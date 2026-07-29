// ABOUTME: Navlib session state machine for 3Dconnexion SpaceMouse support,
// ABOUTME: speaking WAMP v1 to the local 3DxNLServer (dialect: Nl-Proxy 1.4.6).

export const NL_URL = 'wss://127.51.68.120:8182';
export const NL_SUBPROTOCOL = 'wamp';

const WELCOME = 0;
const PREFIX = 1;
const CALL = 2;
const CALL_RESULT = 3;
const SUBSCRIBE = 5;
const EVENT = 8;

// Creates a navlib session. The caller owns the transport: it feeds inbound
// frames to onMessage and provides send/now plus the scene callbacks.
// readProperty(name) returns a value or undefined (answered as null);
// applyUpdate(name, value) receives driver writes; onRegistered fires once
// when the controller instance is live.
export function createSession({ send, now, readProperty, applyUpdate, onRegistered }) {
  let seq = 0;
  let mouseCallId = null;
  let controllerCallId = null;
  let instance = null;

  const call = (proc, ...args) => {
    const id = `c${++seq}`;
    send(JSON.stringify([CALL, id, proc, ...args]));
    return id;
  };

  function onMessage(text) {
    const msg = JSON.parse(text);
    switch (msg[0]) {
      case WELCOME: {
        send(JSON.stringify([PREFIX, '3dx_rpc', 'wss://127.51.68.120/3dconnexion#']));
        send(JSON.stringify([PREFIX, '3dconnexion', 'wss://127.51.68.120/3dconnexion']));
        send(JSON.stringify([PREFIX, 'self', 'spacemouse://local']));
        mouseCallId = call('3dx_rpc:create', '3dconnexion:3dmouse', '0.8.1');
        break;
      }
      case CALL_RESULT: {
        const [, id, result] = msg;
        if (id === mouseCallId && result?.connexion) {
          controllerCallId = call('3dx_rpc:create', '3dconnexion:3dcontroller', result.connexion,
            { version: 0.8, name: 'CADScope', rowMajorOrder: false });
        } else if (id === controllerCallId && result?.instance !== undefined) {
          instance = result.instance;
          send(JSON.stringify([SUBSCRIBE, `3dconnexion:3dcontroller/${instance}`]));
          call('3dx_rpc:update', `3dconnexion:3dcontroller/${instance}`, { focus: true });
          call('3dx_rpc:update', `3dconnexion:3dcontroller/${instance}`, { frame: { timingSource: 1 } });
          onRegistered();
        }
        break;
      }
      case EVENT: {
        const inner = msg[2];
        if (!Array.isArray(inner) || inner[0] !== CALL) break;
        const [, srvId, proc, , prop, value] = inner;
        if (proc.endsWith('read')) {
          const v = readProperty(prop);
          send(JSON.stringify([CALL_RESULT, srvId, v === undefined ? null : v]));
        } else if (proc.endsWith('update')) {
          applyUpdate(prop, value);
          send(JSON.stringify([CALL_RESULT, srvId, {}]));
        }
        break;
      }
    }
  }

  function pumpFrame() {
    if (instance === null) return;
    call('3dx_rpc:update', `3dconnexion:3dcontroller/${instance}`, { frame: { time: now() } });
  }

  return { onMessage, pumpFrame };
}
