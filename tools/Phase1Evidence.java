// Export bounded references from an existing Ghidra analysis database.
// @category i30 Phase 1

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import java.io.BufferedWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.HashSet;
import java.util.Set;

public class Phase1Evidence extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length != 2) {
            throw new IllegalArgumentException("Expected marker TSV and output TSV");
        }
        Path input = Path.of(args[0]);
        Path output = Path.of(args[1]);
        try (BufferedWriter writer = Files.newBufferedWriter(output, StandardCharsets.UTF_8,
                StandardOpenOption.CREATE, StandardOpenOption.APPEND)) {
            for (String line : Files.readAllLines(input, StandardCharsets.UTF_8)) {
                monitor.checkCancelled();
                String[] cells = line.split("\t", 4);
                if (cells.length != 4 || !cells[0].equalsIgnoreCase(currentProgram.getName())) {
                    continue;
                }
                Address target = currentProgram.getImageBase().add(Long.parseUnsignedLong(cells[1], 16));
                Set<Address> seen = new HashSet<>();
                int count = trace(writer, line, target, target, 0, seen);
                if (count == 0) {
                    writer.write(line + "\t" + target + "\t-\t-\t-\t-\n");
                }
            }
        }
    }

    private int trace(BufferedWriter writer, String marker, Address target, Address address,
                      int depth, Set<Address> seen) throws Exception {
        if (!seen.add(address) || seen.size() > 32) {
            return 0;
        }
        int count = 0;
        var refs = currentProgram.getReferenceManager().getReferencesTo(address);
        while (refs.hasNext() && count < 24) {
            monitor.checkCancelled();
            Reference ref = refs.next();
            Address from = ref.getFromAddress();
            Function function = currentProgram.getFunctionManager().getFunctionContaining(from);
            if (function != null) {
                writer.write(marker + "\t" + target + "\t" + from + "\t" + function.getEntryPoint()
                    + "\t" + function.getName() + "\t" + depth + "\n");
                count++;
            } else if (depth < 2 && currentProgram.getMemory().contains(from)) {
                count += trace(writer, marker, target, from, depth + 1, seen);
            }
        }
        return count;
    }
}
