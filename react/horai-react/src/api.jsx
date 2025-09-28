// centralize endpoints so it's easy to flip between localhost/Vercel
export const BACKEND = {
  base: 'https://horai-dun.vercel.app',
  localApi: 'http://localhost:3000', // for POST /api/events in your original code
}

export const endpoints = {
  login: () => `${BACKEND.base}/login`,
  register: () => `${BACKEND.base}/register`,
  calendarToken: () => `${BACKEND.base}/calendarToken`,
  eventsUnified: () => `${BACKEND.base}/getTasks`,
  canvasToken: () => `${BACKEND.base}/canvasToken`,
}
