import test from 'node:test';
import assert from 'node:assert/strict';
import {
  decodeContent, encodeContent, localTime, mergeDeployment, readDeployments, saveDeployment
} from '../site/tracker.mjs';

const item = {
  environment: 'dev', service: 'web-app', version: '1.4.0', status: 'success',
  deployedAt: '2026-11-24T00:00:00Z'
};
const draft = { ...item, deployedAt: '2026-11-24T01:00:00Z', deployedBy: 'octocat' };
const file = data => ({
  encoding: 'base64', content: encodeContent(JSON.stringify(data)), sha: 'latest-sha'
});
const response = (body, status = 200) => new Response(JSON.stringify(body), { status });

test('editing preserves latest unrelated rows and extra fields', () => {
  const original = { ...item, notes: 'keep this' };
  const unrelated = { ...item, environment: 'prod', version: '2.0.0' };
  const latest = [original, unrelated];
  const result = mergeDeployment(latest, original, draft);
  assert.deepEqual(result, [{ ...draft, notes: 'keep this' }, unrelated]);
  assert.equal(latest[0], original);
});

test('creating a deployment and renaming an existing item require a unique environment/service', () => {
  const addition = { ...draft, environment: 'qa', service: 'api' };
  assert.deepEqual(mergeDeployment([item], null, addition), [item, addition]);
  assert.deepEqual(mergeDeployment([item], item, addition), [addition]);
  assert.throws(() => mergeDeployment([item], null, draft), /already exists/);
  assert.throws(() => mergeDeployment([item, addition], item, addition), /already exists/);
});

test('stale edits and deleted items cannot overwrite remote changes', () => {
  assert.throws(() => mergeDeployment([{ ...item, version: '2.0.0' }], item, draft), /changed on GitHub/);
  assert.throws(() => mergeDeployment([], item, draft), /changed on GitHub/);
});

test('invalid inputs are rejected before saving', () => {
  for (const invalid of [
    { ...draft, environment: ' ' }, { ...draft, service: '' },
    { ...draft, version: '' }, { ...draft, deployedBy: ' ' },
    { ...draft, status: 'unknown' }, { ...draft, deployedAt: 'yesterday' }
  ]) {
    assert.throws(() => mergeDeployment([item], item, invalid), Error);
  }
});

test('UTF-8 values survive the GitHub base64 round trip', async () => {
  const data = [{ ...draft, deployedBy: 'Jos\u00e9', service: '\u65e5\u672c' }];
  const encoded = encodeContent(JSON.stringify(data));
  assert.equal(decodeContent(encoded), JSON.stringify(data));
  const result = await readDeployments('', async () => response(file(data)));
  assert.deepEqual(result, { data, sha: 'latest-sha' });
});

test('save reads the latest SHA and commits merged data only to the intended GitHub endpoint', async () => {
  const requests = [];
  const unrelated = { ...item, environment: 'prod', version: '2.0.0' };
  const fetcher = async (url, options) => {
    requests.push({ url, options });
    return response(options.method === 'PUT' ? { commit: { sha: 'new-commit' } } : file([item, unrelated]));
  };
  assert.deepEqual(await saveDeployment('test-token', item, draft, fetcher), draft);
  assert.equal(requests.length, 2);
  for (const { url, options } of requests) {
    assert.equal(new URL(url).origin, 'https://api.github.com');
    assert.equal(options.headers.Authorization, 'Bearer test-token');
    assert.equal(options.credentials, 'omit');
    assert.equal(options.redirect, 'error');
  }
  assert.equal(new URL(requests[0].url).searchParams.get('ref'), 'main');
  const body = JSON.parse(requests[1].options.body);
  assert.equal(body.sha, 'latest-sha');
  assert.equal(body.branch, 'main');
  assert.deepEqual(JSON.parse(decodeContent(body.content)), [draft, unrelated]);
  assert.ok(!requests[1].options.body.includes('test-token'));
});

test('new deployment is committed alongside existing items', async () => {
  const addition = { ...draft, environment: 'qa' };
  let committed;
  const fetcher = async (url, options) => {
    if (options.method !== 'PUT') return response(file([item]));
    committed = JSON.parse(decodeContent(JSON.parse(options.body).content));
    return response({ commit: { sha: 'new-commit' } });
  };
  await saveDeployment('test-token', null, addition, fetcher);
  assert.deepEqual(committed, [item, addition]);
});

test('missing tokens and stale data never issue a write', async () => {
  const calls = [];
  const fetcher = async (url, options) => {
    calls.push(options.method);
    return response(file([{ ...item, version: 'new' }]));
  };
  await assert.rejects(saveDeployment('', item, draft, fetcher), /token first/);
  assert.equal(calls.length, 0);
  await assert.rejects(saveDeployment('test-token', item, draft, fetcher), /changed on GitHub/);
  assert.deepEqual(calls, [undefined]);
});

test('authentication, conflicts, and uncertain network outcomes surface actionable failures', async () => {
  await assert.rejects(readDeployments('bad-token', async () => response({}, 401)), /rejected the token/);
  await assert.rejects(readDeployments('', async () => response({}, 403)), /rate limit/);
  const conflict = async (url, options) => response(options.method === 'PUT' ? {} : file([item]), options.method === 'PUT' ? 409 : 200);
  await assert.rejects(saveDeployment('test-token', item, draft, conflict), /file changed/);
  await assert.rejects(readDeployments('', async () => { throw new TypeError('network'); }), /result is uncertain/);
});

test('malformed reads and unverified save responses cannot report success', async () => {
  await assert.rejects(readDeployments('', async () => response({ content: '' })), /unsupported file/);
  await assert.rejects(readDeployments('', async () => response(file({}))), /must be an array/);
  await assert.rejects(saveDeployment('test-token', item, draft, async (url, options) =>
    response(options.method === 'PUT' ? {} : file([item]))), /verify the item/);
});

test('local datetime values preserve the deployment instant including seconds', () => {
  const iso = '2026-11-24T00:01:02.123Z';
  assert.equal(new Date(localTime(iso)).toISOString(), iso);
});
