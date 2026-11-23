// Collect local decompiler output for selected stock functions.
// @category i30 Phase 1

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;

public class Phase1Functions extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length != 2) {
            throw new IllegalArgumentException("Expected target list and evidence directory");
        }
        var rows = Files.readAllLines(Path.of(args[0]), StandardCharsets.UTF_8);
        var addresses = new ArrayList<String>();
        for (String row : rows) {
            String[] items = row.split("\t");
            if (items.length == 2 && items[0].equalsIgnoreCase(currentProgram.getName())
                    && items[1].matches("[0-9a-fA-F]{1,8}")) {
                addresses.add(items[1]);
            }
        }
        if (addresses.isEmpty()) {
            return;
        }
        Path directory = Path.of(args[1]);
        Files.createDirectories(directory);
        var decompiler = new DecompInterface();
        try {
            if (!decompiler.openProgram(currentProgram)) {
                throw new IllegalStateException("Could not initialize decompiler");
            }
            for (String address : addresses) {
                monitor.checkCancelled();
                Function function = getFunctionAt(toAddr(address));
                if (function == null) {
                    printerr("Function not found at " + address);
                    continue;
                }
                var result = decompiler.decompileFunction(function, 30, monitor);
                if (result.decompileCompleted()) {
                    Files.writeString(directory.resolve(currentProgram.getName() + "-" + address + ".c"),
                        result.getDecompiledFunction().getC(), StandardCharsets.UTF_8);
                } else {
                    printerr(address + ": " + result.getErrorMessage());
                }
            }
        } finally {
            decompiler.dispose();
        }
    }
}
