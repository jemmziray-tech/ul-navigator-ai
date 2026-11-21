import { test } from "node:test";
import assert from "node:assert/strict";
import { comparisonCsv, courseMatches, sourceDate, validCourseIds } from "../src/lib/courses.ts";
const course = { id:"one",title:"Machine Learning and Finance",url:"https://example.test/one",checkedAt:"2026-11-19 12:30:00",level:"Postgraduate",subjects:["Computing & AI"],summary:"Learn statistical models.",code:"TEST1",duration:"One year",attendance:"Part-time",delivery:"Online",nfq:"Level 9",award:"MSc",start:null,points:null,pointsYear:null,links:{},requirements:null };
test("search requires all words and accepts programme codes",()=>{
  assert.equal(courseMatches(course,"finance machine"),true);
  assert.equal(courseMatches(course,"TEST1"),true);
  assert.equal(courseMatches(course,"finance nursing"),false);
});
test("shared and saved selections reject unknown IDs, duplicates and invalid shapes",()=>{
  assert.deepEqual(validCourseIds(["one","unknown","one",null],[course],3),["one"]);
  assert.deepEqual(validCourseIds({ids:["one"]},[course]),[]);
  assert.deepEqual(validCourseIds(["one","two"],[course,{...course,id:"two"}],1),["one"]);
});
test("CSV keeps provenance and safely quotes cells and spreadsheet formulas",()=>{
  const csv=comparisonCsv([{...course,title:'=SUM(1,2) "test"'}]);
  assert.ok(csv.includes("https://example.test/one"));
  assert.ok(csv.includes(`"'=SUM(1,2) ""test"""`));
  assert.ok(csv.includes("2026-11-19 12:30:00"));
  assert.ok(csv.startsWith("\uFEFF"));
});
test("source dates use UTC and handle missing or malformed dates",()=>{
  assert.equal(sourceDate(null),"Date unavailable");
  assert.equal(sourceDate("invalid"),"Date unavailable");
  assert.match(sourceDate(course.checkedAt),/19 Nov 2026/);
});
