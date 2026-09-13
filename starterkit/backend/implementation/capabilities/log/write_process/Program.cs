// Registration-unaware executor for log.write, in C# instead of Python --
// proves a capability can run out-of-process, in a genuinely different
// language (R4/R5). Never imported -- spawned as a separate process,
// reached over loopback TCP.
//
// Connect/parse/dispatch machinery lives in
// ../../../clients/csharp/BridgeClient.cs (a ProjectReference) -- Execute
// below is this capability's ONLY code, a pure function. Nothing here
// writes the connect/read/reply loop; that's BridgeClient.Connection.Serve's
// job, so this file would be identical if log.write were ever reachable
// in-process (a C# Bridge, hypothetically) instead of as its own
// process -- see ../../../../README.md
// "clients/python/direct_adapter.py" for the same property in Python.

using System;
using System.Text.Json;
using BridgeClient;

object Execute(string operation, JsonElement input, Connection conn)
{
    // `message`/`level` aren't checked here -- Bridge.handle already
    // validated both against the contract's declared shape (required,
    // type, default, enum) before sending the invocation, so this is a
    // trusting lookup, not a defensive one.
    var message = input.GetProperty("message").GetString();
    var level = input.GetProperty("level").GetString();
    Console.WriteLine($"[{level!.ToUpperInvariant()}] {message}");
    return new { };
}

Connection.Serve(Execute);
