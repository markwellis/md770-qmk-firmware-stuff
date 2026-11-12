import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Function;
import java.io.PrintWriter;
import java.io.File;
public class ExportMd770 extends GhidraScript {
 public void run() throws Exception {
  DecompInterface di=new DecompInterface();
  di.openProgram(currentProgram);
  File out=new File(getScriptArgs()[0], currentProgram.getName()+".c");
  int count=0;
  try (PrintWriter pw=new PrintWriter(out)) {
   for (Function f:currentProgram.getFunctionManager().getFunctions(true)) {
    DecompileResults r=di.decompileFunction(f,30,monitor);
    pw.println("// "+f.getName()+" @ "+f.getEntryPoint());
    if (r.decompileCompleted()) {pw.println(r.getDecompiledFunction().getC());count++;}
    else pw.println("// Failed: "+r.getErrorMessage());
   }
  }
  di.dispose();
  println("Exported "+count+" functions to "+out);
 }
}
