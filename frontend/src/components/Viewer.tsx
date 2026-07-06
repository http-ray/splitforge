import { useMemo } from "react";
import { Canvas } from "@react-three/fiber";
import { OrbitControls, GizmoHelper, GizmoViewport, Grid } from "@react-three/drei";
import * as THREE from "three";
import { useStore, type Axis, type CutPlane } from "../store/useStore";
import { toBufferGeometry } from "../lib/meshGeometry";
import type { MeshData, Bed, PackResponse } from "../api/client";

// SplitForge treats Z as up (like slicers / CAD), not three.js's default Y-up.
THREE.Object3D.DEFAULT_UP.set(0, 0, 1);

const PART_COLORS = [
  "#4f9dff", "#34d399", "#fbbf24", "#f472b6",
  "#a78bfa", "#22d3ee", "#fb923c", "#a3e635",
];

function overflows(size: THREE.Vector3, bed: Bed): boolean {
  return size.x > bed.x || size.y > bed.y || size.z > bed.z;
}

function ModelMesh({ mesh, bed }: { mesh: MeshData; bed: Bed }) {
  const geometry = useMemo(() => toBufferGeometry(mesh), [mesh]);
  const size = useMemo(
    () => geometry.boundingBox!.getSize(new THREE.Vector3()),
    [geometry]
  );
  const color = overflows(size, bed) ? "#f87171" : "#8aa0b8";
  return (
    <mesh geometry={geometry} castShadow receiveShadow>
      <meshStandardMaterial color={color} metalness={0.1} roughness={0.75} />
    </mesh>
  );
}

/** Cut parts, optionally pushed apart radially from their shared center. */
function PartMeshes({ meshes, explode }: { meshes: MeshData[]; explode: number }) {
  const { geoms, centers, globalCenter } = useMemo(() => {
    const gs = meshes.map(toBufferGeometry);
    const cs = gs.map((g) => g.boundingBox!.getCenter(new THREE.Vector3()));
    const gc = cs
      .reduce((acc, c) => acc.add(c), new THREE.Vector3())
      .multiplyScalar(cs.length ? 1 / cs.length : 0);
    return { geoms: gs, centers: cs, globalCenter: gc };
  }, [meshes]);

  return (
    <>
      {geoms.map((g, i) => {
        const dir = centers[i].clone().sub(globalCenter);
        const offset = dir.multiplyScalar(explode * 1.3);
        return (
          <mesh key={i} geometry={g} position={offset.toArray()} castShadow receiveShadow>
            <meshStandardMaterial
              color={PART_COLORS[i % PART_COLORS.length]}
              metalness={0.1}
              roughness={0.65}
            />
          </mesh>
        );
      })}
    </>
  );
}

/** Parts laid out on one or more print plates per the packing result. */
function BedLayout({
  meshes,
  pack,
  bed,
}: {
  meshes: MeshData[];
  pack: PackResponse;
  bed: Bed;
}) {
  const geoms = useMemo(() => meshes.map(toBufferGeometry), [meshes]);
  const gap = Math.max(bed.x, bed.y) * 0.25;
  const totalW = pack.plateCount * bed.x + (pack.plateCount - 1) * gap;
  const startX = -totalW / 2;

  const plateOrigin = (plate: number): [number, number] => [
    startX + plate * (bed.x + gap),
    -bed.y / 2,
  ];

  return (
    <>
      {Array.from({ length: pack.plateCount }).map((_, p) => {
        const [ox, oy] = plateOrigin(p);
        return (
          <group key={`plate${p}`}>
            <mesh position={[ox + bed.x / 2, oy + bed.y / 2, -0.5]}>
              <boxGeometry args={[bed.x, bed.y, 1]} />
              <meshStandardMaterial color="#161b22" roughness={1} />
            </mesh>
            <lineSegments position={[ox + bed.x / 2, oy + bed.y / 2, 0]}>
              <edgesGeometry args={[new THREE.BoxGeometry(bed.x, bed.y, 0.1)]} />
              <lineBasicMaterial color="#34d399" />
            </lineSegments>
          </group>
        );
      })}

      {pack.placements.map((pl) => {
        const g = geoms[pl.index];
        if (!g) return null;
        const bb = g.boundingBox!;
        const [ox, oy] = plateOrigin(pl.plate);
        const corner = [ox + pl.x, oy + pl.y];
        // Position accounts for optional 90-deg rotation about Z (see pack.py).
        const pos: [number, number, number] = pl.rotated
          ? [corner[0] + bb.max.y, corner[1] - bb.min.x, -bb.min.z]
          : [corner[0] - bb.min.x, corner[1] - bb.min.y, -bb.min.z];
        return (
          <mesh
            key={`part${pl.index}`}
            geometry={g}
            position={pos}
            rotation={[0, 0, pl.rotated ? Math.PI / 2 : 0]}
            castShadow
          >
            <meshStandardMaterial
              color={PART_COLORS[pl.index % PART_COLORS.length]}
              metalness={0.1}
              roughness={0.65}
            />
          </mesh>
        );
      })}
    </>
  );
}

/** Semi-transparent plane showing where a cut will land. */
function CutPlaneMesh({
  plane,
  extent,
  selected,
}: {
  plane: CutPlane;
  extent: number;
  selected: boolean;
}) {
  const axis: Axis = plane.axis;
  const rotation: [number, number, number] =
    axis === "x" ? [0, Math.PI / 2, 0] : axis === "y" ? [Math.PI / 2, 0, 0] : [0, 0, 0];
  const position: [number, number, number] =
    axis === "x" ? [plane.offset, 0, extent / 2] :
    axis === "y" ? [0, plane.offset, extent / 2] :
    [0, 0, plane.offset];
  return (
    <mesh position={position} rotation={rotation}>
      <planeGeometry args={[extent * 1.4, extent * 1.4]} />
      <meshBasicMaterial
        color={selected ? "#ff5d5d" : "#ff9d5d"}
        transparent
        opacity={selected ? 0.34 : 0.16}
        side={THREE.DoubleSide}
        depthWrite={false}
      />
    </mesh>
  );
}

function BuildVolume({ bed }: { bed: Bed }) {
  return (
    <mesh position={[0, 0, bed.z / 2]}>
      <boxGeometry args={[bed.x, bed.y, bed.z]} />
      <meshBasicMaterial color="#34d399" wireframe transparent opacity={0.3} />
    </mesh>
  );
}

function Scene() {
  const mesh = useStore((s) => s.mesh);
  const partMeshes = useStore((s) => s.partMeshes);
  const explode = useStore((s) => s.explode);
  const bed = useStore((s) => s.bedDims());
  const cutPlan = useStore((s) => s.cutPlan);
  const selectedPlaneId = useStore((s) => s.selectedPlaneId);
  const stats = useStore((s) => s.stats);
  const viewMode = useStore((s) => s.viewMode);
  const pack = useStore((s) => s.pack);

  const bedMax = Math.max(bed.x, bed.y);
  const modelHeight = stats ? stats.sizeMm[2] : bedMax;
  const planeExtent = Math.max(bedMax, modelHeight);
  const showingParts = !!partMeshes;
  const bedView = viewMode === "bed" && !!pack;

  const lightPos = (s: number): [number, number, number] => [s, s * 0.6, s * 1.4];

  return (
    <>
      <color attach="background" args={["#0e1116"]} />
      <ambientLight intensity={0.65} />
      <directionalLight position={lightPos(bedMax)} intensity={1.1} />
      <directionalLight position={[-bedMax, -bedMax * 0.5, bedMax]} intensity={0.35} />

      <Grid
        args={[bedMax * 2, bedMax * 2]}
        cellSize={10}
        cellColor="#2a2f3a"
        sectionSize={50}
        sectionColor="#3a4150"
        rotation={[Math.PI / 2, 0, 0]}
        infiniteGrid
        fadeDistance={bedMax * 4}
      />

      {!bedView && <BuildVolume bed={bed} />}

      {bedView ? (
        <BedLayout meshes={partMeshes!} pack={pack!} bed={bed} />
      ) : showingParts ? (
        <PartMeshes meshes={partMeshes} explode={explode} />
      ) : (
        mesh && (
          <>
            <ModelMesh mesh={mesh} bed={bed} />
            {cutPlan.map((p) => (
              <CutPlaneMesh
                key={p.id}
                plane={p}
                extent={planeExtent}
                selected={p.id === selectedPlaneId}
              />
            ))}
          </>
        )
      )}

      <OrbitControls makeDefault target={[0, 0, modelHeight / 3]} />
      <GizmoHelper alignment="bottom-right" margin={[70, 70]}>
        <GizmoViewport axisColors={["#f87171", "#34d399", "#4f9dff"]} labelColor="#0e1116" />
      </GizmoHelper>
    </>
  );
}

export default function Viewer() {
  const bed = useStore((s) => s.bedDims());
  const bedMax = Math.max(bed.x, bed.y);
  const camDist = bedMax * 1.7;
  return (
    <div className="viewer">
      <Canvas
        shadows
        camera={{ position: [camDist, -camDist, camDist * 0.9], fov: 45, near: 1, far: 20000 }}
      >
        <Scene />
      </Canvas>
      <div className="hint">Drag to orbit · scroll to zoom · right-drag to pan</div>
    </div>
  );
}
