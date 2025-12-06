const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

// Create dist directory
if (!fs.existsSync('dist')) {
  fs.mkdirSync('dist');
}

// Run TypeScript compiler
try {
  console.log('Compiling TypeScript...');
  execSync('npx tsc', { stdio: 'inherit' });
  console.log('TypeScript compilation successful.');
} catch (error) {
  console.error('TypeScript compilation failed:', error);
  process.exit(1);
}

// Copy assets to dist
try {
  console.log('Copying assets...');
  const srcAssetsDir = path.join('src', 'assets');
  const distAssetsDir = path.join('dist', 'assets');
  
  if (fs.existsSync(srcAssetsDir)) {
    // Create assets directory in dist if it doesn't exist
    if (!fs.existsSync(distAssetsDir)) {
      fs.mkdirSync(distAssetsDir, { recursive: true });
    }
    
    // Copy all files from src/assets to dist/assets
    const files = fs.readdirSync(srcAssetsDir);
    files.forEach(file => {
      const srcFile = path.join(srcAssetsDir, file);
      const distFile = path.join(distAssetsDir, file);
      fs.copyFileSync(srcFile, distFile);
      console.log(`Copied ${file} to dist/assets/`);
    });
    
    console.log('Assets copied successfully.');
  } else {
    console.log('No assets directory found in src.');
  }
} catch (error) {
  console.error('Failed to copy assets:', error);
  process.exit(1);
}

console.log('Build completed successfully!'); 