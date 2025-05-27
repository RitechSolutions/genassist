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

console.log('Build completed successfully!'); 