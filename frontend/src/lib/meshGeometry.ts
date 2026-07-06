import * as THREE from "three";
import type { MeshData } from "../api/client";

/** Build a three.js BufferGeometry from a flat-array MeshData. */
export function toBufferGeometry(mesh: MeshData): THREE.BufferGeometry {
  const geom = new THREE.BufferGeometry();
  geom.setAttribute(
    "position",
    new THREE.Float32BufferAttribute(mesh.vertices, 3)
  );
  geom.setIndex(mesh.faces);
  geom.computeVertexNormals();
  geom.computeBoundingBox();
  geom.computeBoundingSphere();
  return geom;
}

/** Axis-aligned size of a mesh in model units. */
export function meshSize(mesh: MeshData): THREE.Vector3 {
  const box = new THREE.Box3();
  const v = new THREE.Vector3();
  for (let i = 0; i < mesh.vertices.length; i += 3) {
    v.set(mesh.vertices[i], mesh.vertices[i + 1], mesh.vertices[i + 2]);
    box.expandByPoint(v);
  }
  return box.getSize(new THREE.Vector3());
}
