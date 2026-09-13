// Reference client for the process executor protocol
// (starterkit/schemas/process-executor-protocol.schema.json) -- what a process-kind
// executor (blueprint/2-RULES.md R4/R5) exchanges with the Bridge. `Serve` is the
// intended entry point, not `Connection` directly: a capability hands it
// a pure `Execute(operation, input, conn) -> object` function, and never
// writes the connect/read/dispatch/reply loop itself (see
// ../../capabilities/greeting/compose_process for the pattern).
//
// Lives inside this starter kit, not under backend/runtime/bridge/ (not part of
// the Bridge implementation) and not at the repo root (not shared, ecosystem-level
// infrastructure -- every consumer is a capability inside this one
// starter kit; a real application copies the shape, not this copy). See
// runtime/clients/python/bridge_client.py for the same role in Python.
//
// Uses the framework's real JSON support (System.Text.Json), not
// hand-written field extraction -- required for
// `input.GetProperty("name").GetString()` to actually mean something,
// the same way it does in Python.
//
// A capability's own logic fails a call by throwing CallError itself
// (never returning a status code) -- the idiomatic C# equivalent of the
// Rust client's `Result<Value, CallError>`; `Serve` catches it at the
// top of the loop and relays `code`/`message` to the Bridge as the
// terminal reply, the same as a nested call's own CallError propagates
// unchanged when a capability doesn't catch it itself.

using System;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;

namespace BridgeClient
{
    /// <summary>
    /// The outcome of a failed nested call: the Bridge's own
    /// <c>code</c>/<c>message</c>. Also what a capability's own
    /// <c>Execute</c> throws to fail its own call deliberately --
    /// <see cref="Connection.Serve"/> relays it to the Bridge as the
    /// terminal reply, so a capability never calls
    /// <see cref="Connection.ReplyError"/> directly.
    /// </summary>
    public class CallError : Exception
    {
        public string Code { get; }

        public CallError(string code, string message) : base(message)
        {
            Code = code;
        }
    }

    /// <summary>
    /// One connection to the Bridge -- one worker in a
    /// <c>ProcessExecutorPool</c> (backend/runtime/bridge/process_executor.py).
    /// <see cref="Connect"/> reads <c>ARPAPED_BRIDGE_PORT</c> and connects;
    /// everything else is one invocation's request/reply cycle.
    /// </summary>
    public class Connection
    {
        private readonly StreamReader _reader;
        private readonly StreamWriter _writer;

        private Connection(NetworkStream stream)
        {
            _reader = new StreamReader(stream, Encoding.UTF8);
            _writer = new StreamWriter(stream, new UTF8Encoding(encoderShouldEmitUTF8Identifier: false)) { AutoFlush = true };
        }

        public static Connection Connect()
        {
            var portValue = Environment.GetEnvironmentVariable("ARPAPED_BRIDGE_PORT")
                ?? throw new InvalidOperationException("ARPAPED_BRIDGE_PORT must be set by the Bridge");
            if (!int.TryParse(portValue, out var port))
            {
                throw new InvalidOperationException("ARPAPED_BRIDGE_PORT must be a port number");
            }
            var client = new TcpClient();
            client.Connect(IPAddress.Loopback, port);
            return new Connection(client.GetStream());
        }

        private void WriteValue(object value)
        {
            _writer.Write(JsonSerializer.Serialize(value));
            _writer.Write('\n');
        }

        private JsonElement? ReadValue()
        {
            var line = _reader.ReadLine();
            if (line == null)
            {
                return null;
            }
            using var document = JsonDocument.Parse(line);
            return document.RootElement.Clone();
        }

        /// <summary>
        /// Makes one nested call to another capability, resolved through
        /// this implementation's own declared dependencies (R4). Blocks for
        /// exactly one reply before returning -- a worker connection is
        /// exclusively borrowed for one invocation's whole duration, so that
        /// reply can never be confused with a fresh invocation.
        /// </summary>
        public JsonElement Call(string capabilityId, string operation, object input)
        {
            WriteValue(new { call = new { capability_id = capabilityId, operation, input } });
            var reply = ReadValue()
                ?? throw new CallError("BRIDGE_EXECUTION_FAILED", "connection closed while awaiting the nested call's reply");
            if (reply.TryGetProperty("error", out var error))
            {
                var code = error.TryGetProperty("code", out var codeElement) ? codeElement.GetString() ?? "" : "";
                var message = error.TryGetProperty("message", out var messageElement) ? messageElement.GetString() ?? "" : "";
                throw new CallError(code, message);
            }
            return reply.TryGetProperty("output", out var output) ? output : default;
        }

        public void ReplyOutput(object output) => WriteValue(new { output });

        public void ReplyError(string code, string message) => WriteValue(new { error = new { code, message } });

        /// <summary>
        /// Serves a pure <c>Execute(operation, input, conn) -> object</c>
        /// function over the process executor wire protocol: connects, reads
        /// one invocation per line, calls <c>execute</c>, sends the terminal
        /// reply. <c>execute</c> gets <c>conn</c> only to make its own nested
        /// calls through it (<c>conn.Call(...)</c>, R4) -- a leaf capability
        /// that never calls another capability simply ignores that
        /// parameter. This is the ONLY thing that should ever depend on how
        /// this process is reached: a capability's own <c>Execute</c> is
        /// exactly the same function whether it's compiled straight into a
        /// Bridge (hypothetically) or run as its own process, so changing
        /// how it's reached never touches it -- see
        /// runtime/clients/python/direct_adapter.py for the same property
        /// in Python.
        /// </summary>
        public static void Serve(Func<string, JsonElement, Connection, object> execute)
        {
            var conn = Connect();
            while (true)
            {
                var message = conn.ReadValue();
                if (message == null)
                {
                    return;
                }
                var operation = message.Value.TryGetProperty("operation", out var operationElement)
                    ? operationElement.GetString() ?? ""
                    : "";
                var input = message.Value.TryGetProperty("input", out var inputElement) ? inputElement : default;
                try
                {
                    var output = execute(operation, input, conn);
                    conn.ReplyOutput(output);
                }
                catch (CallError e)
                {
                    conn.ReplyError(e.Code, e.Message);
                }
            }
        }
    }
}
