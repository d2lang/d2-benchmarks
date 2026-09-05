package main

import (
  "encoding/json"
  "fmt"
  "os"
  "path/filepath"

  "github.com/d2lang/d2/d2compiler"
  "github.com/d2lang/d2/d2graph"
)

type Object struct {
  ID string `json:"id"`
  Parent string `json:"parent"`
  Children []string `json:"children"`
  Attr d2graph.Attributes `json:"attributes"`
}
type Edge struct {
  ID string `json:"id"`
  Src string `json:"source"`
  Dst string `json:"target"`
  SrcArrow bool `json:"source_arrow"`
  DstArrow bool `json:"target_arrow"`
  SrcArrowhead *d2graph.Attributes `json:"source_arrowhead,omitempty"`
  DstArrowhead *d2graph.Attributes `json:"target_arrowhead,omitempty"`
  Attr d2graph.Attributes `json:"attributes"`
}
func main() {
  if len(os.Args) < 3 { panic("usage: export OUTPUT_DIR INPUT...") }
  for _, p := range os.Args[2:] {
    f, err := os.Open(p); if err != nil { panic(err) }
    g, config, err := d2compiler.Compile(filepath.Base(p), f, &d2compiler.CompileOptions{FS: os.DirFS(filepath.Dir(p))})
    f.Close(); if err != nil { panic(err) }
    if len(g.Layers)+len(g.Scenarios)+len(g.Steps)>0 || g.Legend!=nil { panic("unsupported extra boards/legend") }
    objects := make([]Object, 0, len(g.Objects))
    for _, obj := range g.Objects {
      o := Object{ID:obj.AbsID(), Attr:obj.Attributes, Children:[]string{}}
      if obj.Parent != nil && obj.Parent != g.Root { o.Parent = obj.Parent.AbsID() }
      for _, child := range obj.ChildrenArray { o.Children=append(o.Children, child.AbsID()) }
      if obj.Class!=nil || obj.SQLTable!=nil { panic("unsupported class/table") }
      objects=append(objects,o)
    }
    edges:=make([]Edge,0,len(g.Edges))
    for _, e := range g.Edges { edges=append(edges,Edge{e.AbsID(),e.Src.AbsID(),e.Dst.AbsID(),e.SrcArrow,e.DstArrow,e.SrcArrowhead,e.DstArrowhead,e.Attributes}) }
    data:=map[string]any{"source":filepath.Base(p),"root_attributes":g.Root.Attributes,"config":config,"objects":objects,"edges":edges}
    b,err:=json.MarshalIndent(data,"","  "); if err!=nil { panic(err) }
    dest:=filepath.Join(os.Args[1],filepath.Base(p)+".graph.json")
    if err=os.WriteFile(dest,append(b,'\n'),0644);err!=nil {panic(err)}
    fmt.Printf("%s: %d objects, %d edges\n",filepath.Base(p),len(objects),len(edges))
  }
}
