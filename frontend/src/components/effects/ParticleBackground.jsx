import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { isWebGLAvailable } from '../../utils/webgl'

export default function ParticleBackground() {
  const mountRef = useRef(null)
  const [hasWebGL, setHasWebGL] = useState(true)

  useEffect(() => {
    if (!isWebGLAvailable()) {
      setHasWebGL(false)
      return
    }

    const mount = mountRef.current
    if (!mount) return

    let renderer
    try {
      // Scene
      const scene = new THREE.Scene()
      const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000)
      camera.position.z = 5

      renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true })
      renderer.setSize(window.innerWidth, window.innerHeight)
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
      renderer.setClearColor(0x000000, 0)
      mount.appendChild(renderer.domElement)

      // Particles
      const particleCount = 120
      const positions = new Float32Array(particleCount * 3)
      const colors = new Float32Array(particleCount * 3)
      const sizes = new Float32Array(particleCount)

      const colorPalette = [
        new THREE.Color('#6172f3'),
        new THREE.Color('#8b5cf6'),
        new THREE.Color('#06b6d4'),
        new THREE.Color('#10b981'),
      ]

      for (let i = 0; i < particleCount; i++) {
        positions[i * 3] = (Math.random() - 0.5) * 20
        positions[i * 3 + 1] = (Math.random() - 0.5) * 12
        positions[i * 3 + 2] = (Math.random() - 0.5) * 10
        const color = colorPalette[Math.floor(Math.random() * colorPalette.length)]
        colors[i * 3] = color.r
        colors[i * 3 + 1] = color.g
        colors[i * 3 + 2] = color.b
        sizes[i] = Math.random() * 0.06 + 0.02
      }

      const geometry = new THREE.BufferGeometry()
      geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3))
      geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3))
      geometry.setAttribute('size', new THREE.BufferAttribute(sizes, 1))

      const material = new THREE.ShaderMaterial({
        vertexShader: `
          attribute float size;
          varying vec3 vColor;
          void main() {
            vColor = color;
            vec4 mvPos = modelViewMatrix * vec4(position, 1.0);
            gl_PointSize = size * (300.0 / -mvPos.z);
            gl_Position = projectionMatrix * mvPos;
          }
        `,
        fragmentShader: `
          varying vec3 vColor;
          void main() {
            float d = distance(gl_PointCoord, vec2(0.5));
            if (d > 0.5) discard;
            float alpha = 1.0 - smoothstep(0.2, 0.5, d);
            gl_FragColor = vec4(vColor, alpha * 0.7);
          }
        `,
        transparent: true,
        vertexColors: true,
        depthWrite: false,
      })

      const particles = new THREE.Points(geometry, material)
      scene.add(particles)

      // Connection lines
      const lineMaterial = new THREE.LineBasicMaterial({
        color: 0x6172f3,
        transparent: true,
        opacity: 0.06,
      })

      const lineGeometry = new THREE.BufferGeometry()
      const linePositions = []

      for (let i = 0; i < particleCount; i++) {
        for (let j = i + 1; j < particleCount; j++) {
          const dx = positions[i * 3] - positions[j * 3]
          const dy = positions[i * 3 + 1] - positions[j * 3 + 1]
          const dz = positions[i * 3 + 2] - positions[j * 3 + 2]
          const dist = Math.sqrt(dx * dx + dy * dy + dz * dz)
          if (dist < 3) {
            linePositions.push(
              positions[i * 3], positions[i * 3 + 1], positions[i * 3 + 2],
              positions[j * 3], positions[j * 3 + 1], positions[j * 3 + 2],
            )
          }
        }
      }

      lineGeometry.setAttribute('position', new THREE.Float32BufferAttribute(linePositions, 3))
      const lines = new THREE.LineSegments(lineGeometry, lineMaterial)
      scene.add(lines)

      // Mouse parallax
      let mouse = { x: 0, y: 0 }
      const onMouseMove = (e) => {
        mouse.x = (e.clientX / window.innerWidth - 0.5) * 0.3
        mouse.y = -(e.clientY / window.innerHeight - 0.5) * 0.3
      }
      window.addEventListener('mousemove', onMouseMove)

      // Resize
      const onResize = () => {
        camera.aspect = window.innerWidth / window.innerHeight
        camera.updateProjectionMatrix()
        renderer.setSize(window.innerWidth, window.innerHeight)
      }
      window.addEventListener('resize', onResize)

      // Animation loop
      let animId
      const clock = new THREE.Clock()
      const animate = () => {
        animId = requestAnimationFrame(animate)
        const t = clock.getElapsedTime()

        particles.rotation.y = t * 0.015 + mouse.x
        particles.rotation.x = t * 0.008 + mouse.y
        lines.rotation.y = particles.rotation.y
        lines.rotation.x = particles.rotation.x

        // Float particles gently
        const pos = geometry.attributes.position
        for (let i = 0; i < particleCount; i++) {
          pos.array[i * 3 + 1] += Math.sin(t + i * 0.5) * 0.0008
        }
        pos.needsUpdate = true

        renderer.render(scene, camera)
      }
      animate()

      return () => {
        cancelAnimationFrame(animId)
        window.removeEventListener('mousemove', onMouseMove)
        window.removeEventListener('resize', onResize)
        if (renderer) renderer.dispose()
        geometry.dispose()
        material.dispose()
        if (mount.contains(renderer.domElement)) {
          mount.removeChild(renderer.domElement)
        }
      }
    } catch (error) {
      console.error('WebGL Initialization failed:', error)
      setHasWebGL(false)
    }
  }, [])

  if (!hasWebGL) {
    return (
      <div className="fixed inset-0 z-0 bg-slate-950 pointer-events-none opacity-40">
        <div className="absolute inset-0 bg-gradient-to-br from-primary-900/20 via-transparent to-accent-purple/20" />
      </div>
    )
  }

  return (
    <div
      ref={mountRef}
      className="fixed inset-0 z-0 pointer-events-none"
      style={{ opacity: 0.6 }}
    />
  )
}
