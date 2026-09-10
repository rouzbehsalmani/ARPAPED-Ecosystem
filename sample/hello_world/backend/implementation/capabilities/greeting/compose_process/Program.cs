// Registration-unaware executor for greeting.compose, in C# instead of
// Python -- proves a process-kind capability can call ANOTHER capability
// through the Bridge (R4/R5), the same mechanism a factory executor gets
// (../compose/executor.py). Never imported -- spawned as a separate
// process, reached over loopback TCP.
//
// Connect/parse/dispatch/nested-call machinery lives in
// ../../../clients/csharp/BridgeClient.cs (a ProjectReference) -- Execute
// below is this capability's ONLY code, a pure function taking `conn`
// solely to make its own nested call through it. Nothing here writes the
// connect/read/reply loop; that's BridgeClient.Connection.Serve's job, so
// this file would be identical if greeting.compose were ever reachable
// in-process (a C# Bridge, hypothetically) instead of as its own
// process -- see ../../../../README.md
// "clients/python/direct_adapter.py" for the same property in Python.

using System.Text.Json;
using BridgeClient;

object Execute(string operation, JsonElement input, Connection conn)
{
    // `name` isn't checked here -- Bridge.handle already validated it
    // (present, string, non-blank via `pattern: "\S"`), so this is a
    // trusting lookup, not a defensive one.
    var name = input.GetProperty("name").GetString();

    // A nested call, resolved through this implementation's own
    // declared dependencies.capabilities (R4) -- console.write isn't
    // imported or spawned by this process itself.
    var text = $"Greetings, {name}!";
    conn.Call("console.write", "write", new { text });
    return new { };
}

Connection.Serve(Execute);
