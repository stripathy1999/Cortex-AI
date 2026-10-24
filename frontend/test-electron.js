console.log("process.type:", process.type);
console.log("process.versions.electron:", process.versions.electron);
const e = require("electron");
console.log("electron type:", typeof e);
console.log("electron.app:", typeof e?.app, e?.app);
if (e?.app) {
  console.log("SUCCESS: app is available");
} else {
  console.log("FAIL: app is not available");
}
