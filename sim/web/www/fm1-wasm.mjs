// fm1-wasm.mjs -- loads fm1.wasm, the virtual FM-1 built standalone by
// Emscripten (no Emscripten JavaScript runtime). Shared by the AudioWorklet
// (worklet.js) and the Node parity test (../test/parity.mjs), so both run the
// module the same way. MIT licence, like the rest of this repository.

// Instantiate from bytes or a compiled module. The build is meant to need no
// imports at all; any it does get a stub that records the call, and
// `imports` lists them so a test can fail on them.
export async function instantiateFm1(source) {
  const module = source instanceof WebAssembly.Module ? source : await WebAssembly.compile(source);
  const wanted = WebAssembly.Module.imports(module);
  const calls = [];
  const imports = {};
  for (const imp of wanted) {
    if (imp.kind !== 'function') throw new Error(`fm1.wasm imports ${imp.module}.${imp.name} (${imp.kind})`);
    imports[imp.module] = imports[imp.module] || {};
    imports[imp.module][imp.name] = (...args) => {
      calls.push(`${imp.module}.${imp.name}`);
      if (imp.name === 'proc_exit') throw new Error(`fm1.wasm exited with ${args[0]}`);
      return 0;
    };
  }
  const instance = await WebAssembly.instantiate(module, imports);
  const ex = instance.exports;
  if (typeof ex._initialize === 'function') ex._initialize();   // static constructors
  return {
    module,
    exports: ex,
    imports: wanted.map((i) => `${i.module}.${i.name}`),
    calls,
    memory: ex.memory,
    // A NUL-terminated ASCII string at `ptr` (TextDecoder is missing in some
    // AudioWorklet scopes).
    string(ptr) {
      const bytes = new Uint8Array(ex.memory.buffer, ptr);
      let s = '';
      for (let i = 0; bytes[i] !== 0; ++i) s += String.fromCharCode(bytes[i]);
      return s;
    },
  };
}

// Panel ids, in fm1_app.h's order.
export const BUTTONS = ['OCT-', 'OCT+', 'FX', 'SEL', 'ENV', 'LFO', 'EDIT', 'GLO',
  'HOME', 'SAVE', 'ARP', 'SEQ', 'PLAY/STOP', 'REC'];
export const ENCODERS = ['SELECT', 'PRESETS', 'ALGORITHM', 'KNOB1', 'KNOB2', 'KNOB3', 'KNOB4'];
export const KEYS = 27;
export const BLOCK = 64;
export const SCREEN = 240;
