# GenAssist Frontend

## 🧩 Project Overview

**GenAssist** is a frontend application built with modern web technologies to support advanced AI‑powered workflows. It integrates with backend services and enables users to manage features like audit logs, conversation transcripts, analytics, agents, tools, knowledge bases, etc., including support for RAG (Retrieval‑Augmented Generation).

---

## 🛠️ Tech Stack

- **Vite** – Fast development and build tool  
- **React** – UI library for building interactive interfaces  
- **TypeScript** – Static typing for safer code  
- **shadcn-ui** – Accessible, customizable UI components  
- **Tailwind CSS** – Utility-first CSS framework for UI 

---

## 🚀 Getting Started

### ✅ Prerequisites

- **Node.js & npm** 
The only requirement is having Node.js & npm installed - [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating)

### 🧑‍💻 Local Setup

1. **Clone the repository**
   ```bash
    git clone <YOUR_REPO_URL>
    cd <YOUR_REPO_NAME>
   ```

2. **Install dependencies**
   ```bash
   npm install
   ```

3. **Start the development server**
   ```bash
   npm run dev
   ```

4. **Open in browser**  
   Visit [http://localhost:8080](http://localhost:8080) (or URL shown in terminal)

---

## 🏗️ Build for Production

To create a production build:
```bash
npm run build
```

To preview the build locally:
```bash
npm run preview
```

---

## 🧪 Development Scripts

| Script              | Description                          |
|---------------------|--------------------------------------|
| `npm run dev`       | Start development server             |
| `npm run build`     | Build the app for production         |
| `npm run preview`   | Preview the production build         |
| `npm run lint`      | Run linter to check code quality     |

---

## 📁 Folder Structure

```
src/
├── components/     # Reusable UI components
├── views/          # Feature-specific pages
├── hooks/          # Custom React hooks
├── services/       # API calls and logic
├── helpers/        # Utility functions
├── interfaces/     # TypeScript types and interfaces
public/             # Static assets
index.html          # App entry point
```

---

## 🎉 Welcome to GenAssist!

We're excited to have you using GenAssist! Whether you're exploring analytics, reviewing conversations, managing agents or knowledge bases, everything is designed to make your experience smooth, powerful, and intuitive. No technical knowledge needed—just jump in and start leveraging the full potential of AI-driven workflows. Let GenAssist do the heavy lifting for you!