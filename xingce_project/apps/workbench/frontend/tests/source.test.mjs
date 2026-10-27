import test from 'node:test';
import assert from 'node:assert/strict';
import {sourceLink} from '../src/logic.mjs';

test('source links preserve verified snapshot and line, encoding the path', () => {
  const commit = '278984401124db40da5163a31275b8deb9c282f4';
  const url = sourceLink({source_commit:commit,source_path:'06-资料分析/测试.md',source_line:87});
  assert.equal(url, `https://github.com/mytangyh/xingcezhenti/blob/${commit}/06-%E8%B5%84%E6%96%99%E5%88%86%E6%9E%90/%E6%B5%8B%E8%AF%95.md#L87`);
});
test('source links reject executable URLs, invalid snapshots and traversal', () => {
  assert.equal(sourceLink({url:'javascript:alert(1)'}), '');
  assert.equal(sourceLink({source_commit:'main',source_path:'x.md'}), '');
  assert.equal(sourceLink({source_commit:'a'.repeat(40),source_path:'../x.md'}), '');
  assert.equal(sourceLink(null), '');
});
