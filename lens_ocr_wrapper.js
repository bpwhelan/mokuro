#!/usr/bin/env node

const Lens = require('chrome-lens-ocr').default || require('chrome-lens-ocr');
const fs = require('fs');

if (process.argv.length < 3) {
    console.error('Usage: node lens_ocr_wrapper.js <image_path>');
    process.exit(1);
}

const imagePath = process.argv[2];

if (!fs.existsSync(imagePath)) {
    console.error(`Error: File ${imagePath} does not exist`);
    process.exit(1);
}

const lens = new Lens();

lens.scanByFile(imagePath)
    .then(result => {
        console.log(JSON.stringify(result));
    })
    .catch(error => {
        console.error(`Error: ${error.message}`);
        process.exit(1);
    }); 