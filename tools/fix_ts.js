const fs = require('fs');
let store = fs.readFileSync('store/useAgentStore.ts', 'utf-8');
store = store.replace(
  '  tool?: string;\n  toolInput?: string;\n}',
  '  tool?: string;\n  toolInput?: string;\n  action_type?: string;\n  action_input?: string;\n}'
);
fs.writeFileSync('store/useAgentStore.ts', store);
