// SPDX-License-Identifier: GPL-2.0-or-later
// Copyright (c) 2023 Hansem Ro <hansemro@outlook.com>

use crate::command::HT32ISPCommand;
use crc::{CRC_16_XMODEM, Crc};
use indicatif::{ProgressBar, ProgressState, ProgressStyle};
use std::fs::File;
use std::io::{Read, Write};
use std::path::PathBuf;
use std::time::{Duration, Instant};

#[derive(Debug)]
#[allow(dead_code)]
pub enum Error {
    Usb(rusb::Error),
    DeviceNotFound,
    EndpointNotFound,
    InvalidResponse,
    ReconnectFailed,
    File(std::io::Error),
    InvalidFilePath,
    WriteFailed,
    CheckFailed,
    OptionBytePageProtected,
    PageProtected(u8),
    StatusTimeout,
}

fn protection_bit(page: u32, model: u32) -> (usize, u32) {
    let pages_per_bit = if matches!(model, 0x52342 | 0x52352) {
        2
    } else {
        1
    };
    let bit = page / pages_per_bit;
    ((bit / 32) as usize, bit % 32)
}

fn checked_flash_end(addr: u32, length: usize, limit: u32) -> Result<usize, Error> {
    if length == 0 || !length.is_multiple_of(4) || !addr.is_multiple_of(4) {
        return Err(Error::InvalidResponse);
    }
    let end = (addr as usize)
        .checked_add(length)
        .ok_or(Error::InvalidResponse)?;
    if end > limit as usize {
        return Err(Error::InvalidResponse);
    }
    Ok(end)
}

fn option_words(pp: [u32; 4], flash_security: bool, ob_protection: bool) -> [(u32, u32); 6] {
    let cp = !((flash_security as u32) | ((ob_protection as u32) << 1));
    let checksum = pp
        .iter()
        .chain(std::iter::once(&cp))
        .fold(0u32, |sum, value| sum.wrapping_add(*value));
    [
        (0, pp[0]),
        (4, pp[1]),
        (8, pp[2]),
        (12, pp[3]),
        (16, cp),
        (32, checksum),
    ]
}

fn valid_option_checksum(data: &[u8; 64]) -> bool {
    let words: Vec<u32> = data[..20]
        .chunks_exact(4)
        .map(|bytes| u32::from_le_bytes(bytes.try_into().unwrap()))
        .collect();
    words.iter().all(|word| *word == u32::MAX)
        || words.iter().fold(0u32, |sum, word| sum.wrapping_add(*word))
            == u32::from_le_bytes(data[32..36].try_into().unwrap())
}

fn status_counts(response: &[u8]) -> Result<(u32, u32), Error> {
    let mut passed = 0;
    let mut failed = 0;
    for byte in response {
        match *byte {
            0 => (),
            0x4f => passed += 1,
            0x46 => failed += 1,
            _ => return Err(Error::InvalidResponse),
        }
    }
    Ok((passed, failed))
}

fn wait_for_status<F>(mut pending: u32, timeout: Duration, mut read: F) -> Result<(), Error>
where
    F: FnMut() -> Result<(u32, u32), Error>,
{
    let deadline = Instant::now() + timeout;
    while pending != 0 {
        let (passed, failed) = match read() {
            Err(Error::Usb(rusb::Error::Pipe)) => (0, 0),
            result => result?,
        };
        if failed != 0 {
            return Err(Error::CheckFailed);
        }
        if passed > pending {
            return Err(Error::InvalidResponse);
        }
        pending -= passed;
        if pending != 0 {
            if Instant::now() >= deadline {
                return Err(Error::StatusTimeout);
            }
            std::thread::sleep(Duration::from_millis(5));
        }
    }
    Ok(())
}

/// HT32 device information
pub struct HT32ISPInfo {
    /// HT32 chip model name in hexadecimal. This may be set to 0 if handling unknown version.
    model: u32,
    /// HT32 ISP version
    version: u16,
    /// Page size in bytes
    page_size: u16,
    /// Flash size in bytes (excluding option bytes page)
    flash_size: u32,
}

impl HT32ISPInfo {
    /// Get HT32 chip model
    pub fn model(&self) -> u32 {
        self.model
    }

    /// Get HT32 ISP version
    pub fn version(&self) -> u16 {
        self.version
    }

    /// Get page size in bytes
    pub fn page_size(&self) -> u16 {
        self.page_size
    }

    /// Get flash size in bytes
    pub fn flash_size(&self) -> u32 {
        self.flash_size
    }
}

/// Option byte base address
pub const OB_ADDR: u32 = 0x1ff00000;

/// HT32 device security information
pub struct HT32Security {
    /// Flash security prevents read access to flash when in debug mode or
    /// booting from SRAM.
    flash_security: bool,
    /// Option byte page write protection. Once set, this bit can only be
    /// cleared with a mass-erase and reset.
    option_byte_protection: bool,
    /// HT32F52342/52352 protection bits cover two consecutive 512-byte pages.
    page_protection: [u32; 4],
    option_control: u32,
    option_checksum: u32,
}

impl HT32Security {
    /// Get flash security status
    pub fn flash_security(&self) -> bool {
        self.flash_security
    }

    /// Get Option byte page protection status
    pub fn option_byte_protection(&self) -> bool {
        self.option_byte_protection
    }

    /// Get page protection words
    pub fn page_protection(&self) -> [u32; 4] {
        self.page_protection
    }
}

/// HT32 device in ISP mode
pub struct HT32ISPDevice {
    handle: Option<rusb::DeviceHandle<rusb::GlobalContext>>,
    vid: u16,
    pid: u16,
    bus_number: u8,
    port_numbers: Vec<u8>,
    interface: u8,
    ep_in: u8,
    ep_out: u8,

    info: Option<HT32ISPInfo>,
    security_info: Option<HT32Security>,
}

impl HT32ISPDevice {
    /// Attempts to open HT32ISPDevice with given `vid` and `pid`.
    pub fn new(
        device: &rusb::Device<rusb::GlobalContext>,
        vid: u16,
        pid: u16,
    ) -> Result<Self, Error> {
        // Find endpoints
        let mut ep_in: Option<u8> = None;
        let mut ep_out: Option<u8> = None;
        let mut interface: Option<u8> = None;
        let device_desc = device.device_descriptor().map_err(Error::Usb)?;
        'outer: for n in 0..device_desc.num_configurations() {
            let config_desc = device.config_descriptor(n).map_err(Error::Usb)?;
            for iface in config_desc.interfaces() {
                for iface_desc in iface.descriptors() {
                    for ep_desc in iface_desc.endpoint_descriptors() {
                        if ep_in.is_none()
                            && ep_desc.direction() == rusb::Direction::In
                            && ep_desc.transfer_type() == rusb::TransferType::Interrupt
                            && ep_desc.max_packet_size() == 64
                        {
                            if interface.is_none() {
                                interface = Some(iface.number());
                            }
                            ep_in = Some(ep_desc.address());
                        } else if ep_out.is_none()
                            && ep_desc.direction() == rusb::Direction::Out
                            && ep_desc.transfer_type() == rusb::TransferType::Interrupt
                            && ep_desc.max_packet_size() == 64
                        {
                            if interface.is_none() {
                                interface = Some(iface.number());
                            }
                            ep_out = Some(ep_desc.address());
                        }
                        if ep_in.is_some() && ep_out.is_some() {
                            break 'outer;
                        }
                    }
                }
            }
        }
        if interface.is_none() || ep_in.is_none() || ep_out.is_none() {
            return Err(Error::EndpointNotFound);
        }
        Ok(Self {
            handle: Some(device.open().map_err(Error::Usb)?),
            vid,
            pid,
            bus_number: device.bus_number(),
            port_numbers: device.port_numbers().map_err(Error::Usb)?,
            interface: interface.unwrap(),
            ep_in: ep_in.unwrap(),
            ep_out: ep_out.unwrap(),
            info: None,
            security_info: None,
        })
    }

    /// Attempt to claim device
    pub fn claim(&mut self) -> Result<(), Error> {
        self.handle
            .as_mut()
            .ok_or(Error::DeviceNotFound)?
            .set_auto_detach_kernel_driver(true)
            .ok();
        self.handle
            .as_mut()
            .ok_or(Error::DeviceNotFound)?
            .claim_interface(self.interface)
            .map_err(Error::Usb)?;
        Ok(())
    }

    /// Attempt to release device
    pub fn release(&mut self) -> Result<(), Error> {
        self.handle
            .as_mut()
            .ok_or(Error::DeviceNotFound)?
            .set_auto_detach_kernel_driver(false)
            .ok();
        self.handle
            .as_mut()
            .ok_or(Error::DeviceNotFound)?
            .release_interface(self.interface)
            .map_err(Error::Usb)?;
        Ok(())
    }

    /// Send `cmd` to ISP device at its output endpoint and returns the number
    /// of bytes successfully transmitted.
    fn send_cmd(&self, cmd: &[u8]) -> Result<usize, Error> {
        // update CRC region
        let mut _cmd = [0u8; 64];
        _cmd[..].copy_from_slice(cmd);
        _cmd[2] = 0;
        _cmd[3] = 0;
        // CRC16 (init=0x0000, poly=0x1021)
        let xmodem = Crc::<u16>::new(&CRC_16_XMODEM);
        let crc = xmodem.checksum(&_cmd);
        _cmd[2] = crc as u8;
        _cmd[3] = (crc >> 8) as u8;
        let length = self
            .handle
            .as_ref()
            .ok_or(Error::DeviceNotFound)?
            .write_interrupt(self.ep_out, &_cmd, Duration::new(1, 0))
            .map_err(Error::Usb)?;
        if length != _cmd.len() {
            return Err(Error::InvalidResponse);
        }
        Ok(length)
    }

    /// Attempt to read data from device's input endpoint
    fn recv(&self, buf: &mut [u8]) -> Result<usize, Error> {
        self.handle
            .as_ref()
            .ok_or(Error::DeviceNotFound)?
            .read_interrupt(self.ep_in, buf, Duration::new(1, 0))
            .map_err(Error::Usb)
    }

    /// Send `cmd` to device and get its `response`
    fn send_recv_cmd(&self, cmd: &[u8], response: &mut [u8]) -> Result<(usize, usize), Error> {
        let sent = self.send_cmd(cmd)?;
        let received = self.recv(response)?;
        self.await_status(1)?;
        Ok((sent, received))
    }

    /// Attempt GET_REPORT request
    pub fn get_report(&self, response: &mut [u8]) -> Result<(u32, u32), Error> {
        // Get_Report request (USB HID version v1.11 spec)
        response.fill(0);
        let length = self
            .handle
            .as_ref()
            .ok_or(Error::DeviceNotFound)?
            .read_control(
                /* bmRequest */
                rusb::request_type(
                    rusb::Direction::In,
                    rusb::RequestType::Class,
                    rusb::Recipient::Interface,
                ),
                /* bRequest */ 0x01,
                /* wValue */ 0x0100,
                /* wIndex */ self.interface as u16,
                response,
                Duration::new(1, 0),
            )
            .map_err(Error::Usb)?;
        if length > response.len() {
            return Err(Error::InvalidResponse);
        }
        status_counts(&response[..length])
    }

    fn clear_status(&self) -> Result<(), Error> {
        let mut response = [0u8; 64];
        match self.get_report(&mut response) {
            Ok((0, 0)) | Err(Error::Usb(rusb::Error::Pipe)) => Ok(()),
            Ok(_) => Err(Error::InvalidResponse),
            Err(error) => Err(error),
        }
    }

    fn await_status(&self, expected: u32) -> Result<(), Error> {
        let mut response = [0u8; 64];
        wait_for_status(expected, Duration::from_secs(10), || {
            self.get_report(&mut response)
        })
    }

    fn read_block(&self, address: u32) -> Result<[u8; 64], Error> {
        let cmd: [u8; 64] = HT32ISPCommand::read_flash_cmd(address, 64).into();
        let mut data = [0u8; 64];
        let (sent, received) = self.send_recv_cmd(&cmd, &mut data)?;
        if sent != 64 || received != 64 {
            return Err(Error::InvalidResponse);
        }
        Ok(data)
    }

    /// Get device information including model, ISP version, page size, and
    /// flash size.
    pub fn get_info(&mut self) -> Result<&HT32ISPInfo, Error> {
        if self.info.is_none() {
            let cmd: [u8; 64] = HT32ISPCommand::info_cmd().into();
            let mut info = [0u8; 64];
            let (sent, received) = self.send_recv_cmd(&cmd[..], &mut info[..])?;
            println!("info_transfer: sent={sent} received={received}");
            println!(
                "info_hex: {}",
                info.iter().map(|b| format!("{b:02x}")).collect::<String>()
            );
            if sent != 64 || received != 64 {
                return Err(Error::InvalidResponse);
            }
            let version: u16 = (info[2] as u16) | ((info[3] as u16) << 8);
            let model: u32 = match version {
                0x100 => (info[0] as u32) | ((info[1] as u32) << 8),
                0x101 | 0x103 => {
                    (info[16] as u32)
                        | ((info[17] as u32) << 8)
                        | ((info[18] as u32) << 16)
                        | ((info[19] as u32) << 24)
                }
                _ => 0,
            };
            let page_size: u16 = (info[6] as u16) | ((info[7] as u16) << 8);
            let flash_page_count: u16 = (info[8] as u16) | ((info[9] as u16) << 8);
            let flash_size: u32 = page_size as u32 * flash_page_count as u32;
            self.info = Some(HT32ISPInfo {
                model,
                version,
                page_size,
                flash_size,
            });
        }
        Ok(self.info.as_ref().unwrap())
    }

    /// Get device flash security and option byte protection status.
    pub fn get_security_info(&mut self) -> Result<&HT32Security, Error> {
        if self.security_info.is_none() {
            let cmd: [u8; 64] = HT32ISPCommand::read_flash_cmd(OB_ADDR, 64).into();
            let mut buf = [0u8; 64];
            let (sent, received) = self.send_recv_cmd(&cmd[..], &mut buf[..])?;
            println!("option_transfer: sent={sent} received={received}");
            println!(
                "option_hex: {}",
                buf.iter().map(|b| format!("{b:02x}")).collect::<String>()
            );
            if sent != 64 || received != 64 {
                return Err(Error::InvalidResponse);
            }
            if !valid_option_checksum(&buf) {
                return Err(Error::InvalidResponse);
            }
            // security/protection is enabled when bit is 0
            let flash_security = (buf[16] & 1) == 0;
            let option_byte_protection = (buf[16] & 2) == 0;
            let page_protection_0: u32 = (buf[0] as u32)
                | ((buf[1] as u32) << 8)
                | ((buf[2] as u32) << 16)
                | ((buf[3] as u32) << 24);
            let page_protection_1: u32 = (buf[4] as u32)
                | ((buf[5] as u32) << 8)
                | ((buf[6] as u32) << 16)
                | ((buf[7] as u32) << 24);
            let page_protection_2: u32 = (buf[8] as u32)
                | ((buf[9] as u32) << 8)
                | ((buf[10] as u32) << 16)
                | ((buf[11] as u32) << 24);
            let page_protection_3: u32 = (buf[12] as u32)
                | ((buf[13] as u32) << 8)
                | ((buf[14] as u32) << 16)
                | ((buf[15] as u32) << 24);
            self.security_info = Some(HT32Security {
                flash_security,
                option_byte_protection,
                option_control: u32::from_le_bytes(buf[16..20].try_into().unwrap()),
                option_checksum: u32::from_le_bytes(buf[32..36].try_into().unwrap()),
                page_protection: [
                    page_protection_0,
                    page_protection_1,
                    page_protection_2,
                    page_protection_3,
                ],
            });
        }
        Ok(self.security_info.as_ref().unwrap())
    }

    /// Print device information
    pub fn print_info(&mut self) -> Result<(), Error> {
        let info = self.get_info()?;
        if info.model() != 0 {
            println!("Model: HT32F{:x}", info.model());
        } else {
            println!("Model: unknown");
        }
        println!("Version: v{:x}", info.version());
        println!("Page size: {} B", info.page_size());
        println!("Flash size: {} B", info.flash_size());
        let info = self.get_security_info()?;
        println!("Flash security: {}", info.flash_security());
        println!("Option byte protection: {}", info.option_byte_protection());
        let page_protection = info.page_protection();
        println!(
            "Page protection: {:#08x} {:#08x} {:#08x} {:#08x}",
            page_protection[0], page_protection[1], page_protection[2], page_protection[3]
        );
        Ok(())
    }

    /// Reset device and attempt to reconnect device
    pub fn reset_reconnect(&mut self) -> Result<(), Error> {
        self.reset_iap()?;
        println!("Waiting for device to reconnect...");

        std::thread::sleep(Duration::new(3, 0));
        // Attempt to reconnect by locating new device handle based on previous
        // bus and port numbers. This works only if BOOT pin(s) are configured
        // to boot into ISP.
        let mut dev_list = rusb::DeviceList::new()
            .map_err(Error::Usb)?
            .iter()
            .filter(|dev| {
                if (dev.bus_number() == self.bus_number)
                    && dev
                        .port_numbers()
                        .is_ok_and(|ports| ports == self.port_numbers)
                {
                    match dev.device_descriptor() {
                        Ok(d) => (d.vendor_id() == self.vid) && (d.product_id() == self.pid),
                        Err(_) => false,
                    }
                } else {
                    false
                }
            })
            .collect::<Vec<_>>();
        if dev_list.is_empty() {
            Err(Error::ReconnectFailed)
        } else {
            self.handle = Some(
                dev_list
                    .remove(0)
                    .open()
                    .map_err(|_| Error::ReconnectFailed)?,
            );
            self.claim()?;
            Ok(())
        }
    }

    /// Reset to application firmware. Works even if BOOT pins are configured
    /// to boot into ISP.
    pub fn reset_app(&mut self) -> Result<(), Error> {
        let cmd: [u8; 64] = HT32ISPCommand::reset_ap_cmd().into();
        self.send_cmd(&cmd[..])?;
        // invalidate handle
        self.release().ok();
        self.handle = None;
        self.info = None;
        self.security_info = None;
        Ok(())
    }

    /// Reset to IAP/ISP firmware depending on how BOOT pins are configured.
    pub fn reset_iap(&mut self) -> Result<(), Error> {
        let cmd: [u8; 64] = HT32ISPCommand::reset_iap_cmd().into();
        self.send_cmd(&cmd[..])?;
        // invalidate handle
        self.release().ok();
        self.handle = None;
        self.info = None;
        self.security_info = None;
        Ok(())
    }

    /// If `write` is true, erase then write binary file to flash starting at
    /// `addr`. If `mass_erase` is true, then wipe entire flash. Otherwise,
    /// erase pages of flash used by the file.
    ///
    /// Otherwise, if `write` is false, then check the region of flash against
    /// the binary file.
    fn write_verify(
        &mut self,
        contents: Vec<u8>,
        addr: u32,
        write: bool,
        mass_erase: bool,
    ) -> Result<Vec<u8>, Error> {
        let info = self.get_info()?;
        let model = info.model();
        let geometry = (info.model(), info.page_size(), info.flash_size());
        let end = checked_flash_end(addr, contents.len(), info.flash_size())?;

        if write & !mass_erase {
            let start_page = addr / (info.page_size() as u32);
            let end_page = (end as u32 - 1) / (info.page_size() as u32);
            // check if range of pages overlap page protected bits
            let security_info = self.get_security_info()?;
            for page in start_page..=end_page {
                let (index, offset) = protection_bit(page, model);
                if index >= security_info.page_protection.len() {
                    return Err(Error::InvalidResponse);
                }
                if (security_info.page_protection[index] & (1 << offset)) == 0 {
                    return Err(Error::PageProtected(page as u8));
                }
            }
        }

        if write {
            if mass_erase {
                // Mass-erase
                println!("Mass-erasing flash...");
                self.mass_erase()?;
                // reset to apply changes to security bits
                println!("Resetting device...");
                self.reset_reconnect()?;
                let fresh = self.get_info()?;
                if (fresh.model(), fresh.page_size(), fresh.flash_size()) != geometry {
                    return Err(Error::InvalidResponse);
                }
                let security = self.get_security_info()?;
                if security.page_protection != [u32::MAX; 4]
                    || security.option_control != u32::MAX
                    || security.option_checksum != u32::MAX
                {
                    return Err(Error::InvalidResponse);
                }
            } else {
                // Page-erase
                println!("Erasing flash page(s)...");
                self.page_erase(addr, contents.len() as u32)?;
            }
            println!(
                "Writing {} bytes to flash region [{:#04x}:{:#04x}]...",
                contents.len(),
                addr,
                end - 1
            );
        } else {
            println!(
                "Verifying flash region [{:#04x}:{:#04x}] against {} input bytes",
                addr,
                end - 1,
                contents.len()
            );
        }

        // clear status
        let mut status = [0u8; 64];
        self.clear_status()?;

        let pb = ProgressBar::new(contents.len() as u64);
        pb.set_style(ProgressStyle::with_template("{spinner:.green} [{elapsed_precise}] [{wide_bar:.cyan/blue}] {bytes}/{total_bytes} ({eta})")
            .unwrap()
            .with_key("eta", |state: &ProgressState, w: &mut dyn std::fmt::Write| {
                write!(w, "{:.1}s", state.eta().as_secs_f64()).unwrap()
            })
            .progress_chars("#>-"));

        let mut count = 0;
        for offset in ((addr as usize)..end).step_by(52) {
            let left = end as u32 - offset as u32;
            let length = if left <= 52 { left } else { 52 };
            let mut data = [0u8; 52];
            let start = offset - addr as usize;
            data[..length as usize].copy_from_slice(&contents[start..start + length as usize]);
            let cmd: [u8; 64] = if write {
                HT32ISPCommand::write_flash_cmd(offset as u32, length, data).into()
            } else {
                HT32ISPCommand::check_flash_cmd(offset as u32, length, data).into()
            };
            self.send_cmd(&cmd[..])?;
            count += 1;
            // check status every 30 write/verify requests
            if left <= 52 || count >= 30 {
                wait_for_status(count, Duration::from_secs(10), || {
                    self.get_report(&mut status)
                })?;
                count = 0;
            }
            pb.set_position(offset as u64 + length as u64 - addr as u64);
        }
        if write {
            pb.finish_with_message("Flashed flash region");
        } else {
            pb.finish_with_message("Verified flash region");
        }
        Ok(contents)
    }

    /// Write binary file to flash starting at `addr`.
    pub fn write(
        &mut self,
        filepath: &PathBuf,
        addr: u32,
        mass_erase: bool,
    ) -> Result<Vec<u8>, Error> {
        let mut file = File::open(filepath).map_err(Error::File)?;
        let metadata = file.metadata().map_err(Error::File)?;
        if !metadata.is_file() {
            return Err(Error::InvalidFilePath);
        }
        let mut contents = Vec::new();
        file.read_to_end(&mut contents).map_err(Error::File)?;
        if contents.len() as u64 != metadata.len() {
            return Err(Error::InvalidResponse);
        }
        self.write_verify(contents, addr, true, mass_erase)
    }

    /// Compare contents of flash to file starting at `addr`.
    pub fn verify(&mut self, expected: Vec<u8>, addr: u32) -> Result<(), Error> {
        let expected = self.write_verify(expected, addr, false, false)?;
        let limit = self.get_info()?.flash_size();
        if !limit.is_multiple_of(64) {
            return Err(Error::InvalidResponse);
        }
        let mut offset = 0usize;
        while offset < expected.len() {
            let current = addr + offset as u32;
            let block = current & !63;
            let skip = (current - block) as usize;
            let length = (64 - skip).min(expected.len() - offset);
            let actual = self.read_block(block)?;
            if actual[skip..skip + length] != expected[offset..offset + length] {
                return Err(Error::CheckFailed);
            }
            offset += length;
        }
        println!("Complete main-flash readback matches input");
        Ok(())
    }

    /// Set flash security, option byte protection, and page protection bits.
    /// Changes get applied on the next reset.
    ///
    /// Cannot set option bytes page if option byte protection is already
    /// enabled.
    pub fn erase_write_option_bytes(
        &mut self,
        pp: [u32; 4],
        flash_security: bool,
        ob_protection: bool,
    ) -> Result<(), Error> {
        let security_info = self.get_security_info()?;
        if security_info.option_byte_protection() {
            return Err(Error::OptionBytePageProtected);
        }
        let words = option_words(pp, flash_security, ob_protection);

        // erase
        println!("Erasing option bytes page...");
        self.page_erase(OB_ADDR, 1)?;

        // write
        println!("Writing option bytes...");
        for (offset, value) in words {
            let mut data = [0xffu8; 52];
            data[..4].copy_from_slice(&value.to_le_bytes());
            let cmd: [u8; 64] = HT32ISPCommand::write_flash_cmd(OB_ADDR + offset, 4, data).into();
            self.send_cmd(&cmd)?;
            self.await_status(1)?;
        }
        let cmd: [u8; 64] = HT32ISPCommand::read_flash_cmd(OB_ADDR, 64).into();
        let mut actual = [0u8; 64];
        let (sent, received) = self.send_recv_cmd(&cmd, &mut actual)?;
        if sent != 64 || received != 64 {
            return Err(Error::InvalidResponse);
        }
        for (offset, value) in words {
            let start = offset as usize;
            if actual[start..start + 4] != value.to_le_bytes() {
                return Err(Error::CheckFailed);
            }
        }
        self.security_info = None;
        println!("Documented protection words and checksum match readback");
        Ok(())
    }

    /// Read `n`-bytes of flash starting at `addr` and write to file.
    pub fn read(&mut self, filepath: &PathBuf, addr: u32, n: u32) -> Result<(), Error> {
        let limit = self.get_info()?.flash_size();
        let end = checked_flash_end(addr, n as usize, limit)? as u32;
        if !limit.is_multiple_of(64) {
            return Err(Error::InvalidResponse);
        }
        let mut file = std::fs::OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(filepath)
            .map_err(Error::File)?;
        println!(
            "Reading flash region [{:#04x}:{:#04x}] to {:?}...",
            addr,
            end - 1,
            filepath
        );

        let pb = ProgressBar::new(n as u64);
        pb.set_style(ProgressStyle::with_template("{spinner:.green} [{elapsed_precise}] [{wide_bar:.cyan/blue}] {bytes}/{total_bytes} ({eta})")
            .unwrap()
            .with_key("eta", |state: &ProgressState, w: &mut dyn std::fmt::Write| {
                write!(w, "{:.1}s", state.eta().as_secs_f64()).unwrap()
            })
            .progress_chars("#>-"));

        // read command seems to only accept lengths that are multiples of 64 bytes
        let mut offset = addr;
        while offset < end {
            let block = offset & !63;
            let skip = (offset - block) as usize;
            let length = (64 - skip).min((end - offset) as usize);
            let buf = self.read_block(block)?;
            file.write_all(&buf[skip..skip + length])
                .map_err(Error::File)?;
            offset += length as u32;
            pb.set_position((offset - addr) as u64);
        }
        file.sync_all().map_err(Error::File)?;
        pb.finish();
        Ok(())
    }

    /// Wipe flash contents, flash security, and page protections.
    pub fn mass_erase(&self) -> Result<(), Error> {
        self.clear_status()?;
        let cmd: [u8; 64] = HT32ISPCommand::mass_erase_cmd().into();
        self.send_cmd(&cmd[..])?;
        self.await_status(1)
    }

    /// Erase pages of flash used by given region `addr` to `addr + n - 1`.
    pub fn page_erase(&self, addr: u32, n: u32) -> Result<(), Error> {
        self.clear_status()?;
        let cmd: [u8; 64] = HT32ISPCommand::page_erase_cmd(addr, n).into();
        self.send_cmd(&cmd[..])?;
        self.await_status(1)
    }
}

/// List of (HT32) devices found with the same VID and PID.
pub struct HT32DeviceList {
    dev_list: Vec<rusb::Device<rusb::GlobalContext>>,
    vid: u16,
    pid: u16,
}

/// List of HT32 devices
impl HT32DeviceList {
    /// Obtain a list of connected devices with matching vid and pid.
    pub fn new(vid: u16, pid: u16) -> Result<Self, Error> {
        Ok(Self {
            dev_list: rusb::DeviceList::new()
                .map_err(Error::Usb)?
                .iter()
                .filter(|dev| match dev.device_descriptor() {
                    Ok(d) => (d.vendor_id() == vid) && (d.product_id() == pid),
                    Err(_) => false,
                })
                .collect::<Vec<_>>(),
            vid,
            pid,
        })
    }

    /// Get number of devices in the list
    pub fn len(&self) -> usize {
        self.dev_list.len()
    }

    /// Get `n`-th HT32ISPDevice in the list
    pub fn get_dev(&mut self, n: usize) -> Result<HT32ISPDevice, Error> {
        if n >= self.len() {
            Err(Error::DeviceNotFound)
        } else {
            Ok(HT32ISPDevice::new(&self.dev_list[n], self.vid, self.pid)?)
        }
    }

    /// Print device list
    pub fn print_list(&self) {
        let mut count = 0;
        for dev in self.dev_list.iter() {
            let device_desc = match dev.device_descriptor() {
                Ok(d) => d,
                Err(_) => continue,
            };

            if let Ok(mut ht32_dev) = HT32ISPDevice::new(dev, self.vid, self.pid) {
                ht32_dev.claim().unwrap();
                let info = ht32_dev.get_info().unwrap();
                let model = if info.model() != 0 {
                    format!("HT32F{:x}", info.model()).to_string()
                } else {
                    String::from("Unknown")
                };

                println!(
                    "Device {}: [{:04x}:{:04x}] Model={} Bus={} Port={} Addr={}",
                    count,
                    device_desc.vendor_id(),
                    device_desc.product_id(),
                    model,
                    dev.bus_number(),
                    dev.port_number(),
                    dev.address()
                );

                ht32_dev.release().unwrap();
                count += 1;
            };
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn protection_bits_cover_page_pairs_for_52352() {
        assert_eq!(protection_bit(23, 0x52352), (0, 11));
        assert_eq!(protection_bit(24, 0x52352), (0, 12));
        assert_eq!(protection_bit(254, 0x52352), (3, 31));
        assert_eq!(protection_bit(63, 0x1654), (1, 31));
    }

    #[test]
    fn flash_range_excludes_option_page_and_invalid_inputs() {
        assert_eq!(checked_flash_end(0, 0x1fe00, 0x1fe00).unwrap(), 0x1fe00);
        for (addr, length) in [(0, 0), (1, 4), (0, 3), (0x1fdfc, 8), (u32::MAX, usize::MAX)] {
            assert!(checked_flash_end(addr, length, 0x1fe00).is_err());
        }
    }

    #[test]
    fn final_batch_requires_every_acknowledgement() {
        assert!(matches!(
            wait_for_status(21, Duration::ZERO, || Ok((0, 0))),
            Err(Error::StatusTimeout)
        ));
        assert!(matches!(
            wait_for_status(21, Duration::ZERO, || Ok((20, 0))),
            Err(Error::StatusTimeout)
        ));
        assert!(wait_for_status(21, Duration::ZERO, || Ok((21, 0))).is_ok());
        assert!(matches!(
            wait_for_status(21, Duration::ZERO, || Ok((22, 0))),
            Err(Error::InvalidResponse)
        ));
        assert!(matches!(
            wait_for_status(21, Duration::ZERO, || Ok((20, 1))),
            Err(Error::CheckFailed)
        ));
        let mut batches = [(10, 0), (11, 0)].into_iter();
        assert!(
            wait_for_status(21, Duration::from_secs(1), || Ok(batches.next().unwrap())).is_ok()
        );
    }

    #[test]
    fn status_parser_rejects_crc_payloads_and_unknown_bytes() {
        assert_eq!(status_counts(&[0x4f, 0x4f, 0, 0x46]).unwrap(), (2, 1));
        assert_eq!(status_counts(&[]).unwrap(), (0, 0));
        assert!(status_counts(&[0xea, 0x6c, 0x4f]).is_err());
    }

    #[test]
    fn original_option_words_use_wrapping_checksum_and_no_reserved_offsets() {
        let words = option_words([0xfffff000, 0xffffffff, 0xffffffff, 0xffffffff], true, true);
        assert_eq!(words.map(|(offset, _)| offset), [0, 4, 8, 12, 16, 32]);
        assert_eq!(words[4], (16, 0xfffffffc));
        assert_eq!(words[5], (32, 0xffffeff9));
    }

    #[test]
    fn invalid_option_checksum_cannot_disable_protection() {
        let mut data = [0xffu8; 64];
        assert!(valid_option_checksum(&data));
        for (offset, value) in option_words([0xfffff000, u32::MAX, u32::MAX, u32::MAX], true, true)
        {
            data[offset as usize..offset as usize + 4].copy_from_slice(&value.to_le_bytes());
        }
        assert!(valid_option_checksum(&data));
        data[32] ^= 1;
        assert!(!valid_option_checksum(&data));
    }
}
