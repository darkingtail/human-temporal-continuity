import { useGLTF } from "@react-three/drei";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { DepthOfField, EffectComposer, Noise, Vignette } from "@react-three/postprocessing";
import { BlendFunction } from "postprocessing";
import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { clone } from "three/examples/jsm/utils/SkeletonUtils.js";

type MemoryWorld3DProps = {
  progress: number;
  activeChapter: number;
};

const PATH = new THREE.CatmullRomCurve3(
  [
    new THREE.Vector3(0, 0, 12),
    new THREE.Vector3(1.2, 0.05, 2),
    new THREE.Vector3(-2.7, 0.2, -10),
    new THREE.Vector3(3.4, 0.05, -23),
    new THREE.Vector3(-3.1, 0.3, -37),
    new THREE.Vector3(2.2, 0.1, -52),
    new THREE.Vector3(-1.4, 0.25, -68),
    new THREE.Vector3(1.8, 0.05, -84),
  ],
  false,
  "catmullrom",
  0.34,
);

const CHAPTER_FOG = [0x1a2020, 0x182021, 0x1c2221, 0x171b1d, 0x202321, 0x1b201d];
const UP = new THREE.Vector3(0, 1, 0);

function journeyPosition(progress: number) {
  return THREE.MathUtils.clamp(0.945 - progress * 0.91, 0.035, 0.945);
}

function seeded(index: number, salt = 0) {
  const value = Math.sin(index * 91.731 + salt * 37.17) * 43758.5453;
  return value - Math.floor(value);
}

function createRoadGeometry(halfWidth = 5.2, yOffset = 0.06) {
  const segments = 240;
  const positions: number[] = [];
  const uvs: number[] = [];
  const indices: number[] = [];
  const center = new THREE.Vector3();
  const tangent = new THREE.Vector3();
  const side = new THREE.Vector3();

  for (let index = 0; index <= segments; index += 1) {
    const t = index / segments;
    PATH.getPointAt(t, center);
    PATH.getTangentAt(t, tangent);
    side.crossVectors(UP, tangent).normalize();
    const width = halfWidth - Math.sin(t * Math.PI) * 0.28;
    const shoulder = Math.sin(t * 38) * 0.08 + Math.sin(t * 91) * 0.035;
    const left = center.clone().addScaledVector(side, width + shoulder);
    const right = center.clone().addScaledVector(side, -width + shoulder);
    left.y += yOffset;
    right.y += yOffset;
    positions.push(left.x, left.y, left.z, right.x, right.y, right.z);
    uvs.push(0, t * 16, 1, t * 16);
    if (index < segments) {
      const offset = index * 2;
      indices.push(offset, offset + 2, offset + 1, offset + 2, offset + 3, offset + 1);
    }
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geometry.setAttribute("uv", new THREE.Float32BufferAttribute(uvs, 2));
  geometry.setIndex(indices);
  geometry.computeVertexNormals();
  return geometry;
}

function createBankGeometry(direction: -1 | 1) {
  const segments = 180;
  const widths = [5.16, 9.5, 18, 34];
  const positions: number[] = [];
  const indices: number[] = [];
  const center = new THREE.Vector3();
  const tangent = new THREE.Vector3();
  const side = new THREE.Vector3();

  for (let segment = 0; segment <= segments; segment += 1) {
    const t = segment / segments;
    PATH.getPointAt(t, center);
    PATH.getTangentAt(t, tangent);
    side.crossVectors(UP, tangent).normalize();

    widths.forEach((width, ring) => {
      const point = center.clone().addScaledVector(side, direction * width);
      const broadWave = Math.sin(t * 19 + ring * 1.7 + direction) * (0.08 + ring * 0.18);
      const smallWave = Math.sin(t * 67 + ring * 2.4) * (0.025 + ring * 0.04);
      point.y += ring === 0 ? -0.03 : -0.16 + broadWave + smallWave;
      positions.push(point.x, point.y, point.z);
    });
  }

  for (let segment = 0; segment < segments; segment += 1) {
    for (let ring = 0; ring < widths.length - 1; ring += 1) {
      const current = segment * widths.length + ring;
      const next = current + widths.length;
      if (direction === 1) {
        indices.push(current, next, current + 1, next, next + 1, current + 1);
      } else {
        indices.push(current, current + 1, next, next, current + 1, next + 1);
      }
    }
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geometry.setIndex(indices);
  geometry.computeVertexNormals();
  return geometry;
}

function createRoadEdge(direction: -1 | 1) {
  const points = Array.from({ length: 96 }, (_, index) => {
    const t = index / 95;
    const center = PATH.getPointAt(t);
    const tangent = PATH.getTangentAt(t).normalize();
    const side = new THREE.Vector3().crossVectors(UP, tangent).normalize();
    const width = 5.2 - Math.sin(t * Math.PI) * 0.28;
    return center.addScaledVector(side, direction * width).add(new THREE.Vector3(0, 0.095, 0));
  });
  return new THREE.TubeGeometry(new THREE.CatmullRomCurve3(points), 190, 0.024, 5, false);
}

function MemoryRoad() {
  const geometry = useMemo(() => createRoadGeometry(), []);
  const leftEdge = useMemo(() => createRoadEdge(-1), []);
  const rightEdge = useMemo(() => createRoadEdge(1), []);
  useEffect(
    () => () => {
      geometry.dispose();
      leftEdge.dispose();
      rightEdge.dispose();
    },
    [geometry, leftEdge, rightEdge],
  );

  return (
    <group>
      <mesh geometry={geometry} receiveShadow>
        <meshStandardMaterial color="#343a36" roughness={0.98} metalness={0} />
      </mesh>
      <mesh geometry={leftEdge}>
        <meshBasicMaterial color="#9aa29d" transparent opacity={0.13} />
      </mesh>
      <mesh geometry={rightEdge}>
        <meshBasicMaterial color="#9aa29d" transparent opacity={0.13} />
      </mesh>
    </group>
  );
}

function Ground() {
  const leftBank = useMemo(() => createBankGeometry(-1), []);
  const rightBank = useMemo(() => createBankGeometry(1), []);
  useEffect(
    () => () => {
      leftBank.dispose();
      rightBank.dispose();
    },
    [leftBank, rightBank],
  );

  return (
    <group>
      <mesh rotation-x={-Math.PI / 2} position={[0, -1.25, -38]} receiveShadow>
        <planeGeometry args={[150, 130, 1, 1]} />
        <meshStandardMaterial color="#080b0b" roughness={1} />
      </mesh>
      <mesh geometry={leftBank} receiveShadow>
        <meshStandardMaterial color="#101514" roughness={1} flatShading />
      </mesh>
      <mesh geometry={rightBank} receiveShadow>
        <meshStandardMaterial color="#0d1211" roughness={1} flatShading />
      </mesh>
    </group>
  );
}

function Forest() {
  const trunks = useRef<THREE.InstancedMesh>(null);
  const leftBranches = useRef<THREE.InstancedMesh>(null);
  const rightBranches = useRef<THREE.InstancedMesh>(null);
  const conifers = useRef<THREE.InstancedMesh>(null);
  const trees = useMemo(
    () =>
      Array.from({ length: 112 }, (_, index) => {
        const t = seeded(index, 11) * 0.98;
        const point = PATH.getPointAt(t);
        const side = index % 2 === 0 ? -1 : 1;
        const distance = 8.2 + seeded(index, 12) * 24;
        const height = 5.5 + seeded(index, 13) * 9;
        return {
          x: point.x + side * distance,
          z: point.z + (seeded(index, 14) - 0.5) * 7,
          height,
          width: 0.11 + seeded(index, 15) * 0.2,
          rotation: seeded(index, 17) * Math.PI,
          evergreen: seeded(index, 18) > 0.72,
        };
      }),
    [],
  );

  useEffect(() => {
    const trunkMesh = trunks.current;
    const leftBranchMesh = leftBranches.current;
    const rightBranchMesh = rightBranches.current;
    const coniferMesh = conifers.current;
    if (!trunkMesh || !leftBranchMesh || !rightBranchMesh || !coniferMesh) return;
    const matrix = new THREE.Matrix4();
    const quaternion = new THREE.Quaternion();
    const position = new THREE.Vector3();
    const scale = new THREE.Vector3();

    trees.forEach((tree, index) => {
      quaternion.setFromEuler(new THREE.Euler(0, tree.rotation, 0));
      position.set(tree.x, tree.height * 0.5 - 0.05, tree.z);
      scale.set(tree.width, tree.height, tree.width);
      matrix.compose(position, quaternion, scale);
      trunkMesh.setMatrixAt(index, matrix);

      const branchLength = tree.height * (0.22 + seeded(index, 21) * 0.13);
      position.set(tree.x - branchLength * 0.25, tree.height * 0.59, tree.z);
      quaternion.setFromEuler(new THREE.Euler(0, tree.rotation, 0.86));
      scale.set(tree.width * 0.52, branchLength, tree.width * 0.52);
      matrix.compose(position, quaternion, scale);
      leftBranchMesh.setMatrixAt(index, matrix);

      position.set(tree.x + branchLength * 0.24, tree.height * 0.75, tree.z);
      quaternion.setFromEuler(new THREE.Euler(0, tree.rotation + 0.7, -0.92));
      scale.set(tree.width * 0.48, branchLength * 0.84, tree.width * 0.48);
      matrix.compose(position, quaternion, scale);
      rightBranchMesh.setMatrixAt(index, matrix);

      position.set(tree.x, tree.height * 0.64, tree.z);
      quaternion.setFromEuler(new THREE.Euler(0, tree.rotation, 0));
      scale.set(tree.evergreen ? 1.25 + seeded(index, 24) : 0.001, tree.evergreen ? tree.height * 0.55 : 0.001, tree.evergreen ? 1.25 + seeded(index, 24) : 0.001);
      matrix.compose(position, quaternion, scale);
      coniferMesh.setMatrixAt(index, matrix);
    });
    trunkMesh.instanceMatrix.needsUpdate = true;
    leftBranchMesh.instanceMatrix.needsUpdate = true;
    rightBranchMesh.instanceMatrix.needsUpdate = true;
    coniferMesh.instanceMatrix.needsUpdate = true;
  }, [trees]);

  return (
    <group>
      <instancedMesh ref={trunks} args={[undefined, undefined, trees.length]} castShadow receiveShadow>
        <cylinderGeometry args={[0.68, 1, 1, 6]} />
        <meshStandardMaterial color="#060908" roughness={1} flatShading />
      </instancedMesh>
      <instancedMesh ref={leftBranches} args={[undefined, undefined, trees.length]} castShadow>
        <cylinderGeometry args={[0.5, 0.82, 1, 5]} />
        <meshStandardMaterial color="#060908" roughness={1} flatShading />
      </instancedMesh>
      <instancedMesh ref={rightBranches} args={[undefined, undefined, trees.length]} castShadow>
        <cylinderGeometry args={[0.5, 0.82, 1, 5]} />
        <meshStandardMaterial color="#060908" roughness={1} flatShading />
      </instancedMesh>
      <instancedMesh ref={conifers} args={[undefined, undefined, trees.length]} castShadow>
        <coneGeometry args={[1, 1, 7]} />
        <meshStandardMaterial color="#0a0e0d" roughness={1} flatShading />
      </instancedMesh>
    </group>
  );
}

function Lamp({ position, height = 3.4 }: { position: [number, number, number]; height?: number }) {
  return (
    <group position={position}>
      <mesh position-y={height / 2} castShadow>
        <cylinderGeometry args={[0.055, 0.09, height, 8]} />
        <meshStandardMaterial color="#080909" roughness={0.9} />
      </mesh>
      <mesh position-y={height}>
        <sphereGeometry args={[0.12, 12, 8]} />
        <meshBasicMaterial color="#d7b579" />
      </mesh>
      <pointLight position-y={height - 0.1} color="#c9ad7a" intensity={5} distance={7} decay={2.2} />
    </group>
  );
}

function Building({ position, scale, roof = true }: { position: [number, number, number]; scale: [number, number, number]; roof?: boolean }) {
  return (
    <group>
      <mesh position={position} scale={scale} castShadow receiveShadow>
        <boxGeometry />
        <meshStandardMaterial color="#090b0c" roughness={1} />
      </mesh>
      {roof ? (
        <mesh
          position={[position[0], position[1] + scale[1] * 0.57, position[2]]}
          rotation-y={Math.PI / 4}
          scale={[scale[0] * 0.78, Math.max(0.7, scale[0] * 0.28), scale[2] * 0.84]}
          castShadow
        >
          <coneGeometry args={[1, 1, 4]} />
          <meshStandardMaterial color="#070909" roughness={1} flatShading />
        </mesh>
      ) : null}
    </group>
  );
}

function ChapterLandmarks() {
  return (
    <group>
      <group position={[0, 0, 4]}>
        <Building position={[-16, 3.2, 0]} scale={[5, 6.5, 4]} />
        <Building position={[17, 4.5, -3]} scale={[5.5, 9, 4.5]} roof={false} />
        <Lamp position={[-5.8, 0, -2]} />
        <Lamp position={[6.4, 0, -5]} />
      </group>

      <group position={[0, 0, -13]}>
        <mesh position={[8, 2.6, 0]} castShadow>
          <boxGeometry args={[8, 0.28, 4.8]} />
          <meshStandardMaterial color="#070909" roughness={1} />
        </mesh>
        <Lamp position={[5.2, 0, 1]} height={3.1} />
        <Lamp position={[10.4, 0, -1.2]} height={3.1} />
      </group>

      <group position={[0, 0, -31]}>
        <Building position={[-18, 3.8, 0]} scale={[5, 7.6, 5]} />
        <Building position={[18, 5.5, -3]} scale={[6, 11, 6]} roof={false} />
        <Building position={[13, 2.7, 5]} scale={[4, 5.4, 3]} />
      </group>

      <group position={[0, 0, -49]}>
        <mesh position={[0, 4.6, 0]} castShadow>
          <torusGeometry args={[5.8, 0.42, 8, 34, Math.PI]} />
          <meshStandardMaterial color="#050707" roughness={1} />
        </mesh>
        <mesh position={[-5.8, 2.3, 0]} castShadow>
          <boxGeometry args={[0.68, 4.6, 1.4]} />
          <meshStandardMaterial color="#050707" roughness={1} />
        </mesh>
        <mesh position={[5.8, 2.3, 0]} castShadow>
          <boxGeometry args={[0.68, 4.6, 1.4]} />
          <meshStandardMaterial color="#050707" roughness={1} />
        </mesh>
        <Lamp position={[-7, 0, 2]} />
        <Lamp position={[7, 0, -2]} />
      </group>

      <group position={[0, 0, -69]}>
        <mesh position={[11, 3.4, 0]} castShadow>
          <torusGeometry args={[3.4, 0.72, 10, 28, Math.PI]} />
          <meshStandardMaterial color="#080a09" roughness={1} />
        </mesh>
        <Building position={[-14, 3.2, -2]} scale={[8, 6.4, 5]} />
      </group>
    </group>
  );
}

function Walker({ progress, reducedMotion }: { progress: number; reducedMotion: boolean }) {
  const group = useRef<THREE.Group>(null);
  const gltf = useGLTF("/models/cesium-man.glb");
  const model = useMemo(() => clone(gltf.scene), [gltf.scene]);
  const mixer = useMemo(() => new THREE.AnimationMixer(model), [model]);
  const blackMaterial = useMemo(
    () => new THREE.MeshStandardMaterial({ color: "#030505", roughness: 0.94, metalness: 0, emissive: "#070a09", emissiveIntensity: 0.18 }),
    [],
  );

  useEffect(() => {
    model.traverse((object) => {
      if (object instanceof THREE.Mesh || object instanceof THREE.SkinnedMesh) {
        object.material = blackMaterial;
        object.castShadow = false;
        object.receiveShadow = true;
      }
    });
    const clip = gltf.animations[0];
    const action = clip ? mixer.clipAction(clip) : null;
    action?.play();
    return () => {
      action?.stop();
      mixer.stopAllAction();
      blackMaterial.dispose();
    };
  }, [blackMaterial, gltf.animations, mixer, model]);

  useFrame(() => {
    const root = group.current;
    if (!root) return;
    const t = journeyPosition(progress);
    const point = PATH.getPointAt(t);
    const tangent = PATH.getTangentAt(t).normalize().multiplyScalar(-1);
    root.position.copy(point);
    root.position.y += 0.08;
    root.rotation.y = Math.atan2(tangent.x, tangent.z);
    const clip = gltf.animations[0];
    if (clip) {
      const duration = Math.max(clip.duration, 0.01);
      const animationTime = reducedMotion ? duration * 0.18 : (progress * duration * 22) % duration;
      mixer.setTime(animationTime);
    }
  });

  return (
    <group ref={group} scale={1.38}>
      <primitive object={model} />
      <mesh position={[0, 0.025, 0]} rotation-x={-Math.PI / 2} receiveShadow>
        <circleGeometry args={[0.52, 28]} />
        <meshBasicMaterial color="#000000" transparent opacity={0.28} depthWrite={false} />
      </mesh>
    </group>
  );
}

function ScrollCamera({ progress, activeChapter }: MemoryWorld3DProps) {
  const { camera, scene, size } = useThree();
  const targetPosition = useMemo(() => new THREE.Vector3(), []);
  const lookAt = useMemo(() => new THREE.Vector3(), []);
  const tangent = useMemo(() => new THREE.Vector3(), []);
  const fogColor = useMemo(() => new THREE.Color(), []);

  useEffect(() => {
    if (!(camera instanceof THREE.PerspectiveCamera)) return;
    camera.fov = size.width < 700 ? 59 : 48;
    camera.updateProjectionMatrix();
  }, [camera, size.width]);

  useFrame((_, delta) => {
    const t = journeyPosition(progress);
    const point = PATH.getPointAt(t);
    PATH.getTangentAt(t, tangent).normalize().multiplyScalar(-1);
    const compact = size.width < 700;
    targetPosition.copy(point).addScaledVector(tangent, compact ? -14.6 : -9.6);
    targetPosition.y += compact ? 6.45 : 4.65;
    const smoothing = 1 - Math.exp(-delta * 4.3);
    camera.position.lerp(targetPosition, smoothing);
    lookAt.copy(point).addScaledVector(tangent, compact ? 9.2 : 8.4);
    lookAt.y += compact ? 1.05 : 0.95;
    camera.lookAt(lookAt);

    const sceneFog = scene.fog;
    if (sceneFog instanceof THREE.FogExp2) {
      fogColor.setHex(CHAPTER_FOG[activeChapter] ?? CHAPTER_FOG[0]);
      sceneFog.color.lerp(fogColor, smoothing * 0.45);
      sceneFog.density = THREE.MathUtils.lerp(sceneFog.density, 0.0175 + activeChapter * 0.0007, smoothing * 0.3);
    }
  });

  return null;
}

function WorldScene({ progress, activeChapter, reducedMotion }: MemoryWorld3DProps & { reducedMotion: boolean }) {
  return (
    <>
      <color attach="background" args={["#151c1b"]} />
      <fogExp2 attach="fog" args={["#1d2523", 0.0175]} />
      <ambientLight color="#b4bdb8" intensity={0.72} />
      <hemisphereLight args={["#bac4bf", "#050606", 0.78]} />
      <directionalLight
        position={[-7, 13, 8]}
        color="#d6ddd8"
        intensity={2.25}
        castShadow
        shadow-mapSize-width={1024}
        shadow-mapSize-height={1024}
        shadow-camera-far={46}
        shadow-camera-left={-22}
        shadow-camera-right={22}
        shadow-camera-top={22}
        shadow-camera-bottom={-22}
      />
      <spotLight position={[3, 9, 9]} target-position={[0, 0, -10]} color="#c6cec9" intensity={28} distance={46} angle={0.42} penumbra={0.86} />

      <Ground />
      <MemoryRoad />
      <Forest />
      <ChapterLandmarks />
      <Walker progress={progress} reducedMotion={reducedMotion} />
      <ScrollCamera progress={progress} activeChapter={activeChapter} />

      <EffectComposer multisampling={0} enableNormalPass={false}>
        <DepthOfField focusDistance={0.018} focalLength={0.032} bokehScale={0.34} />
        <Noise premultiply opacity={0.07} blendFunction={BlendFunction.SOFT_LIGHT} />
        <Vignette eskil={false} offset={0.16} darkness={0.5} />
      </EffectComposer>
    </>
  );
}

export function MemoryWorld3D({ progress, activeChapter }: MemoryWorld3DProps) {
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReducedMotion(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);

  return (
    <div className="memory-world-3d" data-testid="memory-world-3d">
      <Canvas
        aria-hidden="true"
        camera={{ fov: 48, near: 0.1, far: 110, position: [2, 6.5, -96] }}
        dpr={[1, 1.7]}
        shadows="basic"
        gl={{ antialias: true, alpha: false, powerPreference: "high-performance" }}
        fallback={<div className="webgl-fallback">记忆场景无法加载，但时间线内容仍然可以浏览。</div>}
      >
        <Suspense fallback={null}>
          <WorldScene progress={progress} activeChapter={activeChapter} reducedMotion={reducedMotion} />
        </Suspense>
      </Canvas>
      <span className="scene-status" aria-live="polite">
        3D 记忆场景：人物正在第 {activeChapter + 1} 个人生章节中沿道路前行。
      </span>
    </div>
  );
}

useGLTF.preload("/models/cesium-man.glb");
