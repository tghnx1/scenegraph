import http from 'k6/http';
import { check, fail } from 'k6';

const DEFAULT_BASE_URL = 'https://host.docker.internal:8443';
const DASHBOARD_API_PATHS = [
  '/api/admin/composition?include=events%2Cartists%2Cpromoters%2Cvenues',
  '/api/admin/metrics',
  '/api/admin/users/pending',
  '/api/admin/users',
  '/api/admin/artist-claims',
  '/api/admin/activity',
];

const mode = __ENV.SG_K6_MODE || 'dashboard-api';
const vus = Number(__ENV.SG_K6_VUS || '100');
const iterations = Number(__ENV.SG_K6_ITERATIONS || '100');
const maxDuration = __ENV.SG_K6_MAX_DURATION || '5m';
const requestTimeout = __ENV.SG_K6_REQUEST_TIMEOUT || '180s';
const baseUrl = (__ENV.SG_K6_BASE_URL || DEFAULT_BASE_URL).replace(/\/$/, '');
const dashboardPath = __ENV.SG_K6_DASHBOARD_PATH || '/dashboard';
const envFile = __ENV.SG_K6_ENV_FILE || '../.env';

export const options = {
  scenarios: {
    dashboard_load: {
      executor: 'shared-iterations',
      vus,
      iterations,
      maxDuration,
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.05'],
  },
  insecureSkipTLSVerify: true,
};

// Parse the project .env file so the script can authenticate like the frontend does.
function parseEnvFile(path) {
  const values = {};
  const text = open(path);

  for (const rawLine of text.split('\n')) {
    const line = rawLine.trim();
    if (!line || line.startsWith('#') || !line.includes('=')) continue;

    const separatorIndex = line.indexOf('=');
    const key = line.slice(0, separatorIndex).trim();
    const value = line.slice(separatorIndex + 1).trim().replace(/^['"]|['"]$/g, '');
    values[key] = value;
  }

  return values;
}

// Pick explicit k6 env overrides first, then fallback to values from .env.
function getSetting(name, envValues) {
  return (__ENV[name] || envValues[name] || '').trim();
}

const envValues = parseEnvFile(envFile);

// Authenticate once before the load run and share the admin token with virtual users.
export function setup() {
  const username = getSetting('BOOTSTRAP_ADMIN_USERNAME', envValues);
  const password = getSetting('BOOTSTRAP_ADMIN_PASSWORD', envValues);

  if (!username || !password) {
    fail('BOOTSTRAP_ADMIN_USERNAME and BOOTSTRAP_ADMIN_PASSWORD must be set in .env or k6 env vars');
  }

  const response = http.post(
    `${baseUrl}/api/login`,
    JSON.stringify({ username, password }),
    {
      headers: { 'Content-Type': 'application/json' },
      timeout: requestTimeout,
      tags: { endpoint: 'login' },
    },
  );

  const ok = check(response, {
    'login returned 200': (res) => res.status === 200,
    'login returned access token': (res) => Boolean(res.json('access_token')),
  });

  if (!ok) {
    fail(`Login failed: status=${response.status} body=${response.body}`);
  }

  return { token: response.json('access_token') };
}

// Request only the dashboard document. This does not execute frontend JavaScript.
function loadDashboardPage(token) {
  const response = http.get(`${baseUrl}${dashboardPath}`, {
    headers: { Authorization: `Bearer ${token}` },
    timeout: requestTimeout,
    tags: { endpoint: 'dashboard_page' },
  });

  check(response, {
    'dashboard page returned 200': (res) => res.status === 200,
  });
}

// Request the same dashboard API bundle the React dashboard loads after startup.
function loadDashboardApiBundle(token) {
  const params = {
    headers: { Authorization: `Bearer ${token}`, Accept: 'application/json' },
    timeout: requestTimeout,
  };

  const requests = DASHBOARD_API_PATHS.map((path) => [
    'GET',
    `${baseUrl}${path}`,
    null,
    { ...params, tags: { endpoint: path } },
  ]);

  const responses = http.batch(requests);

  for (const response of responses) {
    check(response, {
      [`${response.request.url} returned 200`]: (res) => res.status === 200,
    });
  }
}

// Execute the selected dashboard load mode for one virtual-user iteration.
export default function (data) {
  if (mode === 'page') {
    loadDashboardPage(data.token);
    return;
  }

  if (mode === 'dashboard-api') {
    loadDashboardApiBundle(data.token);
    return;
  }

  fail(`Unsupported SG_K6_MODE=${mode}. Use page or dashboard-api.`);
}
