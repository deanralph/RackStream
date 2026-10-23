import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
test('front projection preserves width, inverts height and ignores depth', () => {
  const { projectPoint } = require('../static/app.js');
  assert.deepEqual(projectPoint([12, 99, 8], 'front'), [12, -8]);
});
test('isometric projection gives rear depth a visible rise and offset', () => {
  const { projectPoint } = require('../static/app.js');
  assert.deepEqual(projectPoint([0, 20, 0]), [10, -9.6]);
  assert.deepEqual(projectPoint([10, 0, 5]), [8.66, -2.1999999999999997]);
});
