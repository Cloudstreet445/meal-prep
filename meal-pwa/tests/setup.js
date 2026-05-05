// Global test setup for meal-pwa
// Runs before each test file in vitest

// Mock window.location so app config initialisation doesn't error
Object.defineProperty(window, 'location', {
  value: {
    hostname: 'localhost',
    search: '',
    href: 'http://localhost/',
  },
  writable: true,
});

// Mock localStorage
const localStorageStore = {};
global.localStorage = {
  getItem: (key) => localStorageStore[key] ?? null,
  setItem: (key, value) => { localStorageStore[key] = String(value); },
  removeItem: (key) => { delete localStorageStore[key]; },
  clear: () => { Object.keys(localStorageStore).forEach(k => delete localStorageStore[k]); },
};
