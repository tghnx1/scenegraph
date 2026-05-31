import { getCssVar } from '../../styles/colors'

function getNodeColor(type: string, isSelected: boolean) {
  if (isSelected) {
    return getCssVar('--selection')
  }

  return getCssVar(`--${type}`)
}

// Draw one graph node with optional opacity for focus/dim rendering.
export const drawNodeShape = (
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  size: number,
  type: string,
  isSelected: boolean,
  opacity = 1,
) => {
  if (x === undefined || y === undefined) return

  ctx.save()
  ctx.translate(x, y)
  ctx.globalAlpha = Math.max(Math.min(opacity, 1), 0)

  const displaySize = isSelected ? size * 1.5 : size
  const color = getNodeColor(type, isSelected)
  ctx.fillStyle = color
  ctx.strokeStyle = isSelected ? color : 'transparent'
  ctx.lineWidth = isSelected ? 3 : 0

  switch (type) {
  case 'event': //round
    ctx.beginPath()
    ctx.arc(0, 0, displaySize, 0, Math.PI * 2)
    ctx.fill()
    ctx.stroke()
    break
  case 'venue': //triangle
    ctx.beginPath()
    ctx.moveTo(0, displaySize)
    ctx.lineTo(-displaySize, -displaySize)
    ctx.lineTo(displaySize, -displaySize)
    ctx.closePath()
    ctx.fill()
    ctx.stroke()
    break
  case 'promoter': //square
    ctx.fillRect(-displaySize, -displaySize, displaySize * 2, displaySize * 2)
    ctx.strokeRect(-displaySize, -displaySize, displaySize * 2, displaySize * 2)
    break
  case 'artist': //hexagonal
    ctx.beginPath()
    for (let i = 0; i < 6; i++) {
  	const angle = (i * Math.PI) / 3
  	const px = Math.cos(angle) * displaySize
  	const py = Math.sin(angle) * displaySize
  	i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py)
    }
    ctx.closePath()
    ctx.fill()
    ctx.stroke()
    break
  }
  ctx.restore()
}
