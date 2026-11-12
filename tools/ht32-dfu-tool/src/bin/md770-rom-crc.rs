// SPDX-License-Identifier: GPL-2.0-or-later

use clap::Parser;
use crc::{CRC_16_XMODEM, Crc};
use std::error::Error;
use std::fs::OpenOptions;
use std::io::Write;
use std::path::PathBuf;
use std::time::{Duration, Instant};

type Result<T> = std::result::Result<T, Box<dyn Error>>;
const TIMEOUT: Duration = Duration::from_secs(2);
const CRC: Crc<u16> = Crc::<u16>::new(&CRC_16_XMODEM);
const IAP_SIZE: usize = 0x3000;
const INFO_ADDRESS: usize = 0x400;
const INFO_HEX: &str = "0400000000000000d9041914c0500404ffffffff01000000ffffffff700100000002e70000024b423034313900000000ffffffff";

#[derive(Parser)]
struct Args {
    /// Decoded stock US 7.02 application, used only for local comparisons.
    image: PathBuf,
    /// Reconstruct and verify the protected 12 KiB stock IAP.
    #[arg(long, value_name = "FILE")]
    dump: Option<PathBuf>,
}

fn decode_hex(value: &str) -> Result<Vec<u8>> {
    if !value.len().is_multiple_of(2) {
        return Err("hex data has an odd length".into());
    }
    value
        .as_bytes()
        .chunks_exact(2)
        .map(|pair| {
            let high = (pair[0] as char).to_digit(16).ok_or("invalid hex digit")?;
            let low = (pair[1] as char).to_digit(16).ok_or("invalid hex digit")?;
            Ok(((high << 4) | low) as u8)
        })
        .collect()
}

fn command(address: u32, length: u32) -> [u8; 64] {
    let mut packet = [0u8; 64];
    packet[0] = 2;
    packet[4..8].copy_from_slice(&address.to_le_bytes());
    packet[8..12].copy_from_slice(&length.to_le_bytes());
    let checksum = CRC.checksum(&packet);
    packet[2..4].copy_from_slice(&checksum.to_le_bytes());
    packet
}

fn status(handle: &rusb::DeviceHandle<rusb::GlobalContext>, interface: u8) -> Result<Vec<u8>> {
    let mut reply = vec![0u8; 64];
    let length = handle.read_control(0xa1, 1, 0x0100, interface.into(), &mut reply, TIMEOUT)?;
    if length > reply.len() {
        return Err(format!("oversized status report: {length}").into());
    }
    reply.truncate(length);
    Ok(reply)
}

fn parse_status(reply: &[u8]) -> Result<Option<u16>> {
    if reply.is_empty() {
        return Ok(None);
    }
    if !(3..=64).contains(&reply.len()) {
        return Err(format!("invalid CRC status length: {}", reply.len()).into());
    }
    if reply.iter().all(|byte| *byte == 0) {
        return Ok(None);
    }
    if reply[2] != 0x4f || reply[3..].iter().any(|byte| *byte != 0) {
        return Err(format!("unexpected CRC status: {reply:02x?}").into());
    }
    Ok(Some(u16::from_le_bytes([reply[0], reply[1]])))
}

fn drain(
    handle: &rusb::DeviceHandle<rusb::GlobalContext>,
    interface: u8,
    verbose: bool,
) -> Result<()> {
    match status(handle, interface) {
        Ok(reply) => {
            if parse_status(&reply)?.is_some() {
                return Err("unexpected pending CRC status before request".into());
            }
        }
        Err(error) if error.downcast_ref::<rusb::Error>() == Some(&rusb::Error::Pipe) => {
            if verbose {
                println!("pre_request_status_stalled=true");
            }
        }
        Err(error) => return Err(error),
    }
    Ok(())
}

fn query(
    handle: &rusb::DeviceHandle<rusb::GlobalContext>,
    interface: u8,
    endpoint: u8,
    address: u32,
    length: u32,
    verbose: bool,
) -> Result<u16> {
    // Draining every command avoids the ROM's finite status queue overflowing.
    drain(handle, interface, verbose)?;
    let packet = command(address, length);
    if verbose {
        println!("sending_crc address={address:#010x} length={length}");
    }
    if handle.write_interrupt(endpoint, &packet, TIMEOUT)? != packet.len() {
        return Err("short CRC request".into());
    }
    let deadline = Instant::now() + TIMEOUT;
    loop {
        std::thread::sleep(Duration::from_millis(5));
        let reply = status(handle, interface)?;
        if let Some(value) = parse_status(&reply)? {
            if verbose {
                println!("crc_status_length={}", reply.len());
            }
            return Ok(value);
        }
        if Instant::now() >= deadline {
            return Err("CRC status timed out".into());
        }
    }
}

fn inverse_tables() -> Result<(Vec<u16>, Vec<u16>)> {
    let mut suffix = vec![0u16; 1 << 16];
    let mut prefix = vec![0u16; 1 << 16];
    let mut suffix_seen = vec![false; 1 << 16];
    let mut prefix_seen = vec![false; 1 << 16];
    for value in 0..=u16::MAX {
        let bytes = value.to_le_bytes();
        let suffix_crc = CRC.checksum(&[0, 0, bytes[0], bytes[1]]) as usize;
        let prefix_crc = CRC.checksum(&[bytes[0], bytes[1], 0, 0]) as usize;
        if suffix_seen[suffix_crc] || prefix_seen[prefix_crc] {
            return Err("CRC inversion table is not one-to-one".into());
        }
        suffix_seen[suffix_crc] = true;
        prefix_seen[prefix_crc] = true;
        suffix[suffix_crc] = value;
        prefix[prefix_crc] = value;
    }
    if suffix_seen.iter().any(|seen| !seen) || prefix_seen.iter().any(|seen| !seen) {
        return Err("CRC inversion table is incomplete".into());
    }
    Ok((suffix, prefix))
}

fn recover_iap<F, P>(mut crc_at: F, mut progress: P) -> Result<Vec<u8>>
where
    F: FnMut(u32, u32) -> Result<u16>,
    P: FnMut(usize, usize),
{
    let info = decode_hex(INFO_HEX)?;
    if info.len() != 52 {
        return Err("invalid information-block anchor".into());
    }
    let (suffix_inverse, prefix_inverse) = inverse_tables()?;
    let mut data = vec![0u8; IAP_SIZE];
    data[INFO_ADDRESS..INFO_ADDRESS + info.len()].copy_from_slice(&info);
    let total = INFO_ADDRESS / 2 + (IAP_SIZE - INFO_ADDRESS - info.len()) / 2;
    let mut done = 0;

    for address in (0..INFO_ADDRESS).step_by(2).rev() {
        let known_suffix = [data[address + 2], data[address + 3]];
        let observed = crc_at(address as u32, 4)?;
        let contribution = CRC.checksum(&[0, 0, known_suffix[0], known_suffix[1]]);
        let value = prefix_inverse[(observed ^ contribution) as usize].to_le_bytes();
        data[address..address + 2].copy_from_slice(&value);
        done += 1;
        progress(done, total);
    }

    for address in (INFO_ADDRESS + info.len() - 2..=IAP_SIZE - 4).step_by(2) {
        let known_prefix = [data[address], data[address + 1]];
        let observed = crc_at(address as u32, 4)?;
        let contribution = CRC.checksum(&[known_prefix[0], known_prefix[1], 0, 0]);
        let value = suffix_inverse[(observed ^ contribution) as usize].to_le_bytes();
        data[address + 2..address + 4].copy_from_slice(&value);
        done += 1;
        progress(done, total);
    }
    if done != total {
        return Err(format!("internal query-count error: {done} != {total}").into());
    }
    Ok(data)
}

fn validate_iap<F>(data: &[u8], mut crc_at: F) -> Result<()>
where
    F: FnMut(u32, u32) -> Result<u16>,
{
    if data.len() != IAP_SIZE {
        return Err("IAP dump has the wrong length".into());
    }
    let info = decode_hex(INFO_HEX)?;
    if data[INFO_ADDRESS..INFO_ADDRESS + info.len()] != info {
        return Err("IAP information block differs from its live read".into());
    }
    let stack = u32::from_le_bytes(data[0..4].try_into()?);
    let reset = u32::from_le_bytes(data[4..8].try_into()?);
    if !(0x2000_0000..=0x2000_4000).contains(&stack) || stack % 4 != 0 {
        return Err(format!("implausible IAP stack pointer: {stack:#010x}").into());
    }
    if reset & 1 == 0 || reset as usize >= IAP_SIZE {
        return Err(format!("implausible IAP reset vector: {reset:#010x}").into());
    }
    for address in (0..IAP_SIZE).step_by(512) {
        let expected = CRC.checksum(&data[address..address + 512]);
        let observed = crc_at(address as u32, 512)?;
        if observed != expected {
            return Err(format!("page CRC mismatch at {address:#06x}").into());
        }
    }
    let expected = CRC.checksum(data);
    let observed = crc_at(0, IAP_SIZE as u32)?;
    if observed != expected {
        return Err("whole-IAP CRC mismatch".into());
    }
    Ok(())
}

fn main() -> Result<()> {
    let args = Args::parse();
    if let Some(path) = &args.dump
        && path.exists()
    {
        return Err(format!("refusing to replace existing file: {}", path.display()).into());
    }
    let image = std::fs::read(args.image)?;
    if image.len() != 49008 || image[..8] != [0xe0, 0x3f, 0, 0x20, 0xc1, 0x32, 0, 0] {
        return Err("expected the decoded right US 7.02 application".into());
    }
    let devices = rusb::devices()?;
    let mut matches = Vec::new();
    for device in devices.iter() {
        let descriptor = device.device_descriptor()?;
        if descriptor.vendor_id() == 0x04d9 && descriptor.product_id() == 0x8010 {
            matches.push(device);
        }
    }
    if matches.len() != 1 {
        return Err(format!("expected one 04d9:8010 ROM device, found {}", matches.len()).into());
    }
    let device = &matches[0];
    let config = device.active_config_descriptor()?;
    let mut transport = None;
    for interface in config.interfaces() {
        for descriptor in interface.descriptors() {
            let endpoints: Vec<_> = descriptor.endpoint_descriptors().collect();
            if let Some(endpoint) = endpoints.iter().find(|endpoint| {
                endpoint.direction() == rusb::Direction::Out
                    && endpoint.transfer_type() == rusb::TransferType::Interrupt
                    && endpoint.max_packet_size() == 64
            }) {
                transport = Some((interface.number(), endpoint.address()));
            }
        }
    }
    let (interface, endpoint) = transport.ok_or("no ROM output endpoint")?;
    println!("interface={interface} output_endpoint={endpoint:#04x}");
    let handle = device.open()?;
    handle.set_auto_detach_kernel_driver(true)?;
    handle.claim_interface(interface)?;
    let result = (|| -> Result<()> {
        let info = decode_hex(INFO_HEX)?;
        let mut samples: Vec<(u32, &[u8])> = vec![
            (0x408, &[0xd9, 0x04, 0x19, 0x14]),
            (0x3000, &[0x1a, 0, 0, 0]),
        ];
        samples.extend(
            [(0, 4), (4, 4), (0, 8), (0, 16), (0, 64), (0xc0, 4), (2, 4)]
                .map(|(offset, length)| (0x3200 + offset as u32, &image[offset..offset + length])),
        );
        samples.push((0x3200, &image[..6]));
        samples.extend((0..info.len() - 3).step_by(2).map(|offset| {
            (
                INFO_ADDRESS as u32 + offset as u32,
                &info[offset..offset + 4],
            )
        }));
        samples.push((INFO_ADDRESS as u32, &info[..6]));
        samples.push((0x408, &info[8..14]));
        for (address, bytes) in samples {
            let length = bytes.len() as u32;
            let observed = query(&handle, interface, endpoint, address, length, true)?;
            println!(
                "address={address:#010x} length={length} local_bytes={bytes:02x?} rom_crc={observed:#06x} local_xmodem={:#06x}",
                CRC.checksum(bytes)
            );
            if observed != CRC.checksum(bytes) {
                return Err("ROM CRC differs from the stock image's CRC16-XMODEM".into());
            }
        }
        Ok(())
    })();
    result?;

    if let Some(path) = args.dump {
        let mut queries = 0;
        let data = recover_iap(
            |address, length| {
                queries += 1;
                query(&handle, interface, endpoint, address, length, false)
            },
            |done, total| {
                if done % 512 == 0 || done == total {
                    println!("recovery_progress={done}/{total}");
                }
            },
        )?;
        println!("recovery_queries={queries}");
        validate_iap(&data, |address, length| {
            query(&handle, interface, endpoint, address, length, false)
        })?;
        let mut output = OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&path)?;
        output.write_all(&data)?;
        output.sync_all()?;
        println!(
            "verified_iap={} bytes output={}",
            data.len(),
            path.display()
        );
    }

    let released = handle.release_interface(interface);
    released?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn crc_request_uses_length_and_xmodem_packet_checksum() {
        let packet = command(0x3202, 4);
        assert_eq!(&packet[..2], &[2, 0]);
        assert_eq!(&packet[4..12], &[2, 0x32, 0, 0, 4, 0, 0, 0]);
        assert_eq!(&packet[2..4], &[0x45, 0x8a]);
        let mut data = packet;
        data[2..4].fill(0);
        assert_eq!(
            u16::from_le_bytes([packet[2], packet[3]]),
            CRC.checksum(&data)
        );
    }

    #[test]
    fn crc_bytes_can_equal_status_markers() {
        let mut reply = [0u8; 64];
        reply[..3].copy_from_slice(&[0x4f, 0x46, 0x4f]);
        assert_eq!(parse_status(&reply).unwrap(), Some(0x464f));
        assert_eq!(parse_status(&reply[..3]).unwrap(), Some(0x464f));
        assert_eq!(parse_status(&[]).unwrap(), None);
        assert!(parse_status(&reply[..2]).is_err());
        assert!(parse_status(&[0; 65]).is_err());
        assert_eq!(parse_status(&[0; 64]).unwrap(), None);
        reply[3] = 0x4f;
        assert!(parse_status(&reply).is_err());
        reply.fill(0);
        reply[0] = 0x46;
        assert!(parse_status(&reply).is_err());
    }

    #[test]
    fn reconstructs_the_iap_from_four_byte_crcs() {
        let mut source: Vec<u8> = (0..IAP_SIZE)
            .map(|index| ((index * 73) ^ (index >> 3)) as u8)
            .collect();
        let info = decode_hex(INFO_HEX).unwrap();
        source[INFO_ADDRESS..INFO_ADDRESS + info.len()].copy_from_slice(&info);
        let mut queries = 0;
        let recovered = recover_iap(
            |address, length| {
                assert_eq!(length, 4);
                queries += 1;
                let address = address as usize;
                Ok(CRC.checksum(&source[address..address + length as usize]))
            },
            |_, _| {},
        )
        .unwrap();
        assert_eq!(recovered, source);
        assert_eq!(queries, 6118);
    }
}
