/**
 * k6 压测模板 — 对齐 seckill_finance_system（openapi）
 * 默认引擎参考：load-testing/执行/SKILL.md
 *
 * 运行：
 *   k6 run output/seckill_load.js
 *   BASE_URL=http://your-server:5001 k6 run output/seckill_load.js
 */
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '30s', target: 10 },
    { duration: '2m', target: 50 },
    { duration: '5m', target: 200 },
    { duration: '30s', target: 0 },
  ],
  thresholds: {
    http_req_duration: ['p(95)<500', 'p(99)<1000'],
    http_req_failed: ['rate<0.01'],
  },
};

// Docker 默认 5001；本地 Flask 常用 5000
const BASE_URL = __ENV.BASE_URL || 'http://your-server:5001';
// seckill_finance_system Docker 常无 /api/health，根路径 / 返回 200
const HEALTH_PATH = __ENV.HEALTH_PATH || '/';
const USERNAME = __ENV.TEST_USERNAME || 'admin';
const PASSWORD = __ENV.TEST_PASSWORD || 'admin123';

const JSON_HEADERS = { 'Content-Type': 'application/json' };

let authToken = null;

function login() {
  const res = http.post(
    `${BASE_URL}/api/auth/login`,
    JSON.stringify({ username: USERNAME, password: PASSWORD }),
    { headers: JSON_HEADERS, tags: { name: 'login' } },
  );
  const ok = check(res, {
    '登录 HTTP 200': (r) => r.status === 200,
    '登录返回 token': (r) => {
      try {
        return r.json('token') !== undefined && r.json('token') !== null;
      } catch (_) {
        return false;
      }
    },
  });
  if (ok) {
    authToken = res.json('token');
  }
  return ok;
}

export default function () {
  const roll = Math.random() * 10;

  // 权重 ~2：健康检查（无需登录）
  if (roll < 2) {
    const res = http.get(`${BASE_URL}${HEALTH_PATH}`, { tags: { name: 'health' } });
    check(res, { '健康检查 200': (r) => r.status === 200 });
    sleep(0.5);
    return;
  }

  // 权重 ~3：登录（或刷新 token）
  if (!authToken || roll < 5) {
    login();
    sleep(0.5);
    return;
  }

  // 权重 ~5：商品列表（可选带 Token）
  const headers = authToken ? { Authorization: `Bearer ${authToken}` } : {};
  const res = http.get(`${BASE_URL}/api/products`, {
    headers,
    tags: { name: 'products_list' },
  });
  check(res, { '商品列表 200': (r) => r.status === 200 });

  // 抽样：已登录时查 Profile
  if (authToken && Math.random() < 0.2) {
    const profile = http.get(`${BASE_URL}/api/auth/profile`, {
      headers: { Authorization: `Bearer ${authToken}` },
      tags: { name: 'profile' },
    });
    check(profile, { 'Profile 200': (r) => r.status === 200 });
  }

  sleep(1);
}

export function handleSummary(data) {
  return {
    stdout: JSON.stringify(
      {
        p95_ms: data.metrics.http_req_duration.values['p(95)'],
        error_rate: data.metrics.http_req_failed.values.rate,
      },
      null,
      2,
    ),
  };
}
