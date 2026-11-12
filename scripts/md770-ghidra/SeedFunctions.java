import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import java.math.BigInteger;

public class SeedFunctions extends GhidraScript {
    public void run() throws Exception {
        for (String argument : getScriptArgs()) {
            Address address = toAddr(Long.decode(argument));
            if (getInstructionAt(address) == null) {
                currentProgram.getProgramContext().setValue(
                    currentProgram.getProgramContext().getRegister("TMode"),
                    address, address, BigInteger.ONE);
                disassemble(address);
            }
            if (getFunctionAt(address) == null) {
                createFunction(address, null);
            }
        }
    }
}
