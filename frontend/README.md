# FaceTimeOS Frontend

*Last Updated: February 14, 2026*

Electron-based UI for FaceTimeOS that provides a floating command bar to control the AI agent, view screenshots, and monitor task execution in real-time.

## 🚀 Quick Start Guide

### Prerequisites
- Node.js (LTS) installed on your computer
- Git installed on your computer
- A REST backend that handles chat/agent commands (the bundled proxy forwards to `http://localhost:5000` by default)

### Installation Steps

1. Clone the repository:
```bash
cd frontend
```

2. Install dependencies:
```bash
# If you encounter Sharp/Python build errors, use this:
SHARP_IGNORE_GLOBAL_LIBVIPS=1 npm install --ignore-scripts
npm rebuild sharp

# Or for normal installation:
npm install
```

### Running the App

#### Method 1: Development Mode (Recommended for first run)
1. Start the development server:
```bash
npm start
```

This command automatically:
- Starts the Vite dev server on port 5180
- Waits for the server to be ready
- Launches the Electron app

#### Method 2: Production Build
```bash
npm run dist
```
The built app will be in the `release` folder.

### ⚠️ Important Notes

1. **Closing the App**: 
   - Press `Cmd + Q` (Mac) or `Ctrl + Q` (Windows/Linux) to quit
   - Or use Activity Monitor/Task Manager to close the app
   - The X button currently doesn't work (known issue)

2. **If the app doesn't start**:
   - Make sure no other app is using port 5180
   - Try killing existing processes:
     ```bash
     # Find processes using port 5180
     lsof -i :5180
     # Kill them (replace [PID] with the process ID)
     kill [PID]
     ```
   - Ensure your REST backend is reachable (defaults to `http://localhost:5000`)

3. **Keyboard Shortcuts**:
   - `Cmd/Ctrl + B`: Toggle window visibility
   - `Cmd/Ctrl + H`: Take screenshot
   - 'Cmd/Enter': Get solution
   - `Cmd/Ctrl + Arrow Keys`: Move window

## 🔧 Troubleshooting

### Windows Issues Fixed 
- **UI not loading**: Port mismatch resolved
- **Electron crashes**: Improved error handling  
- **Build failures**: Production config updated
- **Window focus problems**: Platform-specific fixes applied

### Ubuntu/Linux Issues Fixed 
- **Window interaction**: Fixed focusable settings
- **Installation confusion**: Clear setup instructions
- **Missing dependencies**: All requirements documented

### Common Solutions

#### Sharp/Python Build Errors
If you see `gyp ERR! find Python` or Sharp build errors:
```bash
# Solution 1: Use prebuilt binaries
rm -rf node_modules package-lock.json
SHARP_IGNORE_GLOBAL_LIBVIPS=1 npm install --ignore-scripts
npm rebuild sharp

# Solution 2: Or install Python (if you prefer building from source)
brew install python3  # macOS
# Then run: npm install
```

#### General Installation Issues
If you see other errors:
1. Delete the `node_modules` folder
2. Delete `package-lock.json` 
3. Run `npm install` again
4. Try running with `npm start`

### Platform-Specific Notes
- **Windows**: App now works on Windows 10/11
- **Ubuntu/Linux**: Tested on Ubuntu 20.04+ and most Linux distros  
- **macOS**: Native support with proper window management

## Key Features

- **Floating Command Bar** – Always-on-top interface that keeps agent controls within reach without blocking your workspace.
- **Screenshot Queue Management** – Capture, preview, and prune queued screenshots with keyboard shortcuts and a compact gallery.
- **REST Agent Bridge** – Sends REST calls (`/api/chat`, `/api/pause`, `/api/resume`, `/api/stop`) through the bundled proxy so you can drive any backend workflow.
- **Live Status Updates** – Listens for `/api/currentaction` webhooks and streams updates into the command bar and history view.
- **Toast Notifications & Shortcuts** – Built-in feedback, queue reset tooling, and window positioning shortcuts for quick control.

## Use Cases

### **Academic & Learning**
```
✓ Live presentation support during classes
✓ Quick research during online exams  
✓ Language translation and explanations
✓ Math and science problem solving
```

### **Professional Meetings**
```
✓ Sales call preparation and objection handling
✓ Technical interview coaching
✓ Client presentation support
✓ Real-time fact-checking and data lookup
```

### **Development & Tech**
```
✓ Debug error messages instantly
✓ Code explanation and optimization
✓ Documentation and API references
✓ Algorithm and architecture guidance
```

## 📄 License

ISC License - Free for personal and commercial use.

---

### 🏷️ Tags
`ai-assistant` `facetime` `imessage` `voice-control` `electron-app` `cross-platform` `open-source` `rest-api` `screenshot-management` `mac-automation`
