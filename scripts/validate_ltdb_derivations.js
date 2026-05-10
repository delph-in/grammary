#!/usr/bin/env node

const fs = require("fs");
const readline = require("readline");
const {
  layoutTree,
  maxLeafDepth,
  parseDerivation,
} = require("../assets/ltdb/ltdb-tree.js");

function collectLeaves(node, leaves) {
  if (node.leaf) {
    leaves.push(node);
    return;
  }
  (node.children || []).forEach((child) => collectLeaves(child, leaves));
}

async function main() {
  const input = fs.createReadStream(process.argv[2], { encoding: "utf8" });
  const rl = readline.createInterface({ input, crlfDelay: Infinity });
  let count = 0;
  for await (const line of rl) {
    if (!line) continue;
    const item = JSON.parse(line);
    const tree = parseDerivation(item.deriv);
    if (!tree.name) {
      throw new Error(`missing root name for ${item.db}:${item.example_id}`);
    }
    if (maxLeafDepth(tree, 0) < 1) {
      throw new Error(`missing leaves for ${item.db}:${item.example_id}`);
    }
    const layout = layoutTree(tree);
    const leaves = [];
    collectLeaves(tree, leaves);
    const leafColumns = new Set(leaves.map((leaf) => leaf._y));
    if (leafColumns.size !== 1) {
      throw new Error(`unaligned leaves for ${item.db}:${item.example_id}`);
    }
    if (!layout.nodes.length || !layout.links.length) {
      throw new Error(`empty layout for ${item.db}:${item.example_id}`);
    }
    count += 1;
  }
  console.log(`validated ${count} derivations`);
}

main().catch((error) => {
  console.error(error.stack || error.message);
  process.exit(1);
});
