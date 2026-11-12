import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.mem.MemoryBlock;
import java.math.BigInteger;
public class PrepareMd770 extends GhidraScript {
 public void run() throws Exception {
  for (MemoryBlock block : currentProgram.getMemory().getBlocks()) {
   block.setWrite(false); block.setExecute(true);
  }
  MemoryBlock ram = createMemoryBlock("SRAM", toAddr(0x20000000L), null, 0x4000, false);
  ram.setWrite(true);
  MemoryBlock peripherals = createMemoryBlock("Peripherals", toAddr(0x40000000L), null, 0x100000, false);
  peripherals.setWrite(true);
  peripherals.setVolatile(true);
  MemoryBlock system = createMemoryBlock("System", toAddr(0xe000e000L), null, 0x2000, false);
  system.setWrite(true);
  system.setVolatile(true);
  Address base=currentProgram.getMinAddress();
  for (int i=1;i<48;i++) {
   long v=getInt(base.add(i*4)) & 0xffffffffL;
   Address a=toAddr(v & ~1L);
   if ((v & 1)==0 || !currentProgram.getMemory().contains(a)) continue;
   if (getInstructionAt(a) == null) {
    currentProgram.getProgramContext().setValue(currentProgram.getProgramContext().getRegister("TMode"),a,a,BigInteger.ONE);
    disassemble(a);
   }
   if (getFunctionAt(a)==null) createFunction(a,i==1?"Reset_Handler":String.format("vector_%02d",i));
  }
 }
}
