# CrickCoder Release v0.1.0

**Date:** 2026-02-03
**Tag:** `v0.1.0`
**Status:** Alpha Release

---

## 🚀 Summary
This release makes CrickCoder fully **portable** and introduces the powerful **Template Engine**, transforming how the AI Architect builds interfaces. It also includes critical updates to the **Planner Agent** to prevent improved reasoning flows and a revamped **Electron Build** configuration for easy distribution.

---

## ✨ Key Features

### 1. Template Engine & Librarian
A new "Knowledge Base" for UI templates and components.
- **Global Template Storage**: Templates are now stored globally in `~/.crickcoder/knowledge_base`, decoupled from specific projects.
- **Smart RAG (Retrieval-Augmented Generation)**: The new `CrickCoderTemplateTools` uses LanceDB to perform semantic searches on installed templates.
- **AI-Powered Filtering**: A dedicated ephemeral agent (`Template Architect`) filters search results to find the *exact* component needed for a specific user query.
- **Installation**: One-click installation of template assets into the active project via the new `install_template` tool.

### 2. New Templates Library UI
A dedicated panel in the Frontend (`TemplatesPanel.tsx`) to manage your design assets.
- **Visual Gallery**: Browse installed templates with preview images, version, and author info.
- **Drag & Drop Upload**: Easily install new templates by dropping a ZIP file.
- **Real-time Logs**: Watch the extraction, validation, and indexing process via live SSE logs.
- **Metadata Support**: Reads `manifest.json` from templates to display rich metadata.

### 3. DeepSeek Planner v2
Significant improvements to the Planner Agent's prompt (`prompts/deepseek/planner.md`).
- **Analysis-Only Mode**: The Planner now intelligently detects when you just want information ("Analyze", "Explain") and skips the unnecessary "Execution Plan" generation.
- **Execution Plan (Optional)**: Planning steps are only generated when there is a clear intent to modify code.
- **Reasoning Protocols**: Enhanced chain-of-thought rules for better dependency mapping.

### 4. Portable Windows Build
- **Zip Target**: The Electron build process now produces a **Portable ZIP** file instead of an NSIS installer. This allows for "Plug & Play" usage without administrative privileges.
- **Output Directory**: Builds are located in `crick-ui/release`.

---

## 🛠 Technical Improvements

- **Backend Architecture**:
    - Refactored `server.py` to support global asset serving.
    - Added `template_indexer.py` for automated LanceDB indexing of uploaded ZIPs.
    - Implemented `chunker.py` and `theme_chunker.py` for smarter code splitting during ingestion.

- **Frontend Architecture**:
    - Added `templateService.ts` for standardized API communication.
    - Enhanced `useChat` hook to support global settings.
    - Improved Dark Mode consistency in the new Templates UI.

- **Dependencies**:
    - Added `lancedb` for vector storage.
    - Upgraded `electron-builder` configuration.

---

## 📖 Quick Start

### Building the Release
```bash
cd crick-ui
npm run electron:build
```
*Output: `crick-ui/release/CrickCoder-0.1.0-win.zip`*

### Using Templates
1. Open the **Templates Library** from the sidebar.
2. Drag & drop a Template ZIP file.
3. Ask the Agent: *"Create a login page using the modern-dark template"* -> The Architect will now verify the template's existence and use its assets.
