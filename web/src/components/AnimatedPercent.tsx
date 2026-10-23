import { useEffect } from 'react'
import { animate, motion, useMotionValue, useTransform } from 'motion/react'
import { pct } from '../lib/format'

// A percentage that counts smoothly to its new value
export default function AnimatedPercent({ value, digits = 1, className }: { value: number; digits?: number; className?: string }) {
  const motionValue = useMotionValue(value)
  const text = useTransform(motionValue, (v) => pct(v, digits))

  useEffect(() => {
    const controls = animate(motionValue, value, { duration: 0.6, ease: [0.22, 1, 0.36, 1] })
    return () => controls.stop()
  }, [motionValue, value])

  return <motion.span className={className}>{text}</motion.span>
}
