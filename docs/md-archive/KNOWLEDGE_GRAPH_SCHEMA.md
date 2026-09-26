# Knowledge Graph Schema

## Code Nodes (codebase-memory-mcp)
File     id: file:<path>
Function id: func:<path>:<name>
Class    id: class:<path>:<name>
Module   id: mod:<path>
Service  id: svc:<name>

## Repo Nodes (GitHub API)
Repo     id: repo:<owner>/<name>
Branch   id: branch:<name>
Commit   id: commit:<sha>
PR       id: pr:<number>
Issue    id: issue:<number>
Release  id: rel:<tag>
Author   id: author:<login>
Label    id: label:<name>

## Code Edges
calls      : Function → Function
imports    : File → File
extends    : Class → Class
belongs_to : Function → Class
part_of    : File → Module

## Repo Edges
authored    : Author → Commit/PR/Issue
changed     : Commit → File
merged_into : PR → Branch
fixes       : PR → Issue
tagged      : Release → Commit
parent_of   : Commit → Commit
labels      : Issue → Label

## Query Patterns
Understanding:
  "How does X work?"   → find func nodes matching X, traverse calls
  "What depends on Y?" → reverse-traverse calls + imports from Y
  "Show architecture"  → top-level modules + imports edges
  "Who wrote X?"       → file/func → changed ← commit → authored

Tracking:
  "What changed since T?" → commit nodes where timestamp > T
  "Breaking changes?"     → commits with BREAKING or !:

## Rendering Rules (React Flow)
Default: top-level modules + imports (10–20 nodes)
Color: File=blue, Function=green, Commit=orange, PR=purple
Cap: never render > 100 nodes; cluster by module
