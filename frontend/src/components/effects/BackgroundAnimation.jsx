import { motion } from 'framer-motion'
import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { isWebGLAvailable } from '../../utils/webgl'

export default function BackgroundAnimation() {
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
      // Scene setup
      const scene = new THREE.Scene()
      const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000)
      camera.position.z = 12

      renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true })
      renderer.setSize(window.innerWidth, window.innerHeight)
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
      mount.appendChild(renderer.domElement)

      // ... existing geometry and material logic ...
      const geometry = new THREE.PlaneGeometry(30, 20, 64, 64)
      
      const material = new THREE.ShaderMaterial({
        uniforms: {
          time: { value: 0 },
          color1: { value: new THREE.Color('#6172f3') },
          color2: { value: new THREE.Color('#8b5cf6') },
          color3: { value: new THREE.Color('#06b6d4') },
          color4: { value: new THREE.Color('#10b981') },
        },
        vertexShader: `
          varying vec2 vUv;
          varying float vElevation;
          uniform float time;
          
          vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
          vec2 mod289(vec2 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
          vec3 permute(vec3 x) { return mod289(((x*34.0)+1.0)*x); }
          float snoise(vec2 v) {
            const vec4 C = vec4(0.211324865405187, 0.366025403784439, -0.577350269189626, 0.024390243902439);
            vec2 i  = floor(v + dot(v, C.yy) );
            vec2 x0 = v -   i + dot(i, C.xx);
            vec2 i1;
            i1 = (x0.x > x0.y) ? vec2(1.0, 0.0) : vec2(0.0, 1.0);
            vec4 x12 = x0.xyxy + C.xxzz;
            x12.xy -= i1;
            i = mod289(i);
            vec3 p = permute( permute( i.y + vec3(0.0, i1.y, 1.0 )) + i.x + vec3(0.0, i1.x, 1.0 ));
            vec3 m = max(0.5 - vec3(dot(x0,x0), dot(x12.xy,x12.xy), dot(x12.zw,x12.zw)), 0.0);
            m = m*m ;
            m = m*m ;
            vec3 x = 2.0 * fract(p * C.www) - 1.0;
            vec3 h = abs(x) - 0.5;
            vec3 ox = floor(x + 0.5);
            vec3 a0 = x - ox;
            m *= 1.79284291400159 - 0.85373472095314 * ( a0*a0 + h*h );
            vec3 g;
            g.x  = a0.x  * x0.x  + h.x  * x0.y;
            g.yz = a0.yz * x12.xz + h.yz * x12.yw;
            return 130.0 * dot(m, g);
          }

          void main() {
            vUv = uv;
            float elevation = snoise(vec2(position.x * 0.15 + time * 0.1, position.y * 0.15 + time * 0.1)) * 1.5;
            elevation += snoise(vec2(position.x * 0.3 - time * 0.2, position.y * 0.3 + time * 0.15)) * 0.8;
            vElevation = elevation;
            vec3 newPosition = position;
            newPosition.z += elevation;
            gl_Position = projectionMatrix * modelViewMatrix * vec4(newPosition, 1.0);
          }
        `,
        fragmentShader: `
          uniform vec3 color1;
          uniform vec3 color2;
          uniform vec3 color3;
          uniform vec3 color4;
          uniform float time;
          varying vec2 vUv;
          varying float vElevation;
          void main() {
            float mixStrength = (vElevation + 2.3) / 4.6;
            vec3 colorA = mix(color1, color2, vUv.x + sin(time * 0.5) * 0.2);
            vec3 colorB = mix(color3, color4, vUv.y + cos(time * 0.3) * 0.2);
            vec3 finalColor = mix(colorA, colorB, mixStrength);
            float alpha = 0.4 + smoothstep(-0.5, 0.5, mixStrength) * 0.3;
            float dist = distance(vUv, vec2(0.5));
            alpha *= smoothstep(0.0, 0.4, dist);
            gl_FragColor = vec4(finalColor, alpha);
          }
        `,
        transparent: true,
        depthWrite: false,
      })

      const plane = new THREE.Mesh(geometry, material)
      plane.rotation.x = -Math.PI / 4
      scene.add(plane)

      const particleCount = 200
      const particleGeometry = new THREE.BufferGeometry()
      const particlePositions = new Float32Array(particleCount * 3)
      for(let i = 0; i < particleCount * 3; i+=3) {
        particlePositions[i] = (Math.random() - 0.5) * 30
        particlePositions[i+1] = (Math.random() - 0.5) * 30
        particlePositions[i+2] = (Math.random() - 0.5) * 20
      }
      particleGeometry.setAttribute('position', new THREE.BufferAttribute(particlePositions, 3))
      const particleMaterial = new THREE.PointsMaterial({
        color: 0xffffff,
        size: 0.05,
        transparent: true,
        opacity: 0.4,
        blending: THREE.AdditiveBlending
      })
      const particles = new THREE.Points(particleGeometry, particleMaterial)
      scene.add(particles)

      let mouseX = 0, mouseY = 0
      const handleMouseMove = (e) => {
        mouseX = (e.clientX / window.innerWidth) * 2 - 1
        mouseY = -(e.clientY / window.innerHeight) * 2 + 1
      }
      window.addEventListener('mousemove', handleMouseMove)

      const handleResize = () => {
        camera.aspect = window.innerWidth / window.innerHeight
        camera.updateProjectionMatrix()
        renderer.setSize(window.innerWidth, window.innerHeight)
      }
      window.addEventListener('resize', handleResize)

      const clock = new THREE.Clock()
      let rafId
      const animate = () => {
        rafId = requestAnimationFrame(animate)
        const elapsedTime = clock.getElapsedTime()
        material.uniforms.time.value = elapsedTime
        camera.position.x += (mouseX * 2 - camera.position.x) * 0.05
        camera.position.y += (mouseY * 2 - camera.position.y) * 0.05
        camera.lookAt(scene.position)
        particles.rotation.y = elapsedTime * 0.05
        particles.rotation.x = elapsedTime * 0.02
        renderer.render(scene, camera)
      }
      animate()

      return () => {
        cancelAnimationFrame(rafId)
        window.removeEventListener('mousemove', handleMouseMove)
        window.removeEventListener('resize', handleResize)
        geometry.dispose()
        material.dispose()
        particleGeometry.dispose()
        particleMaterial.dispose()
        if (renderer) renderer.dispose()
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
      <div className="absolute inset-0 overflow-hidden pointer-events-none z-0">
        <div className="absolute inset-0 bg-[#0d0d12] z-[-1]" />
        <div className="absolute inset-0 bg-gradient-to-br from-primary-900/10 via-transparent to-accent-purple/10 opacity-50" />
      </div>
    )
  }

  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none z-0">
      <div className="absolute inset-0 bg-[#0d0d12] z-[-1]" />
      <div ref={mountRef} className="absolute inset-0 mix-blend-screen opacity-80" />
      <div className="absolute inset-x-0 bottom-0 h-1/3 bg-gradient-to-t from-[#0d0d12] to-transparent z-10" />
      <div className="absolute inset-y-0 left-0 w-1/4 bg-gradient-to-r from-[#0d0d12] to-transparent z-10 hidden lg:block" />
    </div>
  )
}
