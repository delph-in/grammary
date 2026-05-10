#!/usr/bin/env node

const assert = require("assert/strict");
const {
  boxWidthForLabel,
  classifyNode,
  isHighlightedNode,
  labelForNode,
  layoutTree,
  parseDerivation,
  rootShapePoints,
  typeHrefForNode,
} = require("../assets/ltdb/ltdb-tree.js");

function collectLeaves(node, leaves = []) {
  if (node.leaf) {
    leaves.push(node);
  }
  (node.children || []).forEach((child) => collectLeaves(child, leaves));
  return leaves;
}

function findNode(node, name) {
  if (node.name === name) {
    return node;
  }
  for (const child of node.children || []) {
    const found = findNode(child, name);
    if (found) {
      return found;
    }
  }
  return null;
}

function testAceLeafShape() {
  const tree = parseDerivation(
    '(root_strict (0 rule 0 0 1 (0 lex-entry 0 0 1 ("word" 42 "token"))))'
  );
  assert.equal(tree.name, "root_strict");
  assert.deepEqual(
    collectLeaves(tree).map((leaf) => leaf.name),
    ["word"]
  );
}

function testCompactLeafShape() {
  const tree = parseDerivation(
    '(20 subj-head 0 0 2 (9 saya 0 0 1 ("SAYA")) (10 makan 0 1 2 ("MAKAN")))'
  );
  assert.equal(tree.name, "subj-head");
  assert.deepEqual(
    collectLeaves(tree).map((leaf) => leaf.name),
    ["SAYA", "MAKAN"]
  );
}

function testVerticalLayoutAndLeafBaseline() {
  const tree = parseDerivation(
    '(root (0 left 0 0 1 ("a" 1 "token")) (0 right 0 1 2 (0 deep 0 1 2 ("b" 2 "token"))))'
  );
  layoutTree(tree);
  const leaves = collectLeaves(tree);
  assert.equal(new Set(leaves.map((leaf) => leaf._y)).size, 1);
  assert.equal(tree._y, 28);
  assert.ok(Math.max(...leaves.map((leaf) => leaf._y)) > tree._y);
  assert.ok(findNode(tree, "left")._x < findNode(tree, "right")._x);
}

function testCollapsedInternalNodeStaysAtOwnDepth() {
  const tree = parseDerivation(
    '(root (0 left 0 0 1 ("a" 1 "token")) (0 right 0 1 2 (0 deep 0 1 2 ("b" 2 "token"))))'
  );
  const right = findNode(tree, "right");
  right.collapsed = true;
  const layout = layoutTree(tree);
  const visibleNames = layout.nodes.map((node) => node.name);
  assert.deepEqual(visibleNames.sort(), ["a", "left", "right", "root"]);
  assert.ok(right._y < collectLeaves(tree)[0]._y);
}

function testNodeBoxesUseLabels() {
  const tree = parseDerivation(
    '(root (0 long_type_name 0 0 1 ("lemma" 1 "token")))'
  );
  layoutTree(tree);
  const leaf = collectLeaves(tree)[0];
  assert.equal(labelForNode(leaf), "lemma");
  assert.equal(labelForNode(tree), "root");
  assert.ok(tree._boxWidth >= boxWidthForLabel("root"));
  assert.equal(leaf._boxHeight, 24);
}

function testShiftClickHrefDoesNotCheckTypeExistence() {
  assert.equal(
    typeHrefForNode({ name: "sb-hd_mc_c", entity: "sb-hd_mc_c" }, {
      typeBaseHref: ".",
    }),
    "./sb-hd_mc_c.html"
  );
  assert.equal(
    typeHrefForNode({ name: "head subject", entity: "head subject" }, {
      typeBaseHref: "./",
    }),
    "./head%20subject.html"
  );
}

function testNodeClassificationAndHighlight() {
  assert.equal(classifyNode({ name: "root_strict" }), "root");
  assert.equal(classifyNode({ name: "root_inffrag" }), "root");
  assert.equal(classifyNode({ name: "hd-cmp_u_c" }), "rule");
  assert.equal(
    classifyNode({ name: "dog_n1", children: [{ name: "dogs", leaf: true }] }),
    "lex-entry"
  );
  assert.equal(classifyNode({ name: "n_pl_olr" }), "lex-rule");
  assert.equal(classifyNode({ name: "v_np_le" }), "lex-type");
  assert.equal(classifyNode({ name: "word", leaf: true }), "lemma");
  assert.equal(
    isHighlightedNode({ name: "hd-cmp_u_c" }, { highlightType: "hd-cmp_u_c" }),
    true
  );
  assert.equal(
    isHighlightedNode({ name: "hd-cmp_u_c" }, { highlightType: "n_pl_olr" }),
    false
  );
}

function testRootShapePoints() {
  const points = rootShapePoints(80, 24).split(" ");
  assert.equal(points.length, 8);
  assert.deepEqual(points, [
    "-30,-12",
    "30,-12",
    "40,-7",
    "40,7",
    "30,12",
    "-30,12",
    "-40,7",
    "-40,-7",
  ]);
}

testAceLeafShape();
testCompactLeafShape();
testVerticalLayoutAndLeafBaseline();
testCollapsedInternalNodeStaysAtOwnDepth();
testNodeBoxesUseLabels();
testShiftClickHrefDoesNotCheckTypeExistence();
testNodeClassificationAndHighlight();
testRootShapePoints();

console.log("ltdb tree tests passed");
