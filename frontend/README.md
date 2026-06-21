# Citadel Frontend

Advanced Next.js frontend for the Citadel cryptographic security gateway.

## Visual Aesthetic: Gilded Noir

A chiaroscuro-inspired design system featuring:

- **Deep Void Black Background**: `#0a0a0a` - Crushing obsidian darkness
- **Neon Accents**:
  - **Amber** (`#FCD34D`) - Warnings and critical alerts
  - **Cyan** (`#06B6D4`) - Cryptographic success and validation
  - **Emerald** (`#10B981`) - Secure operations and confirmations
- **Oversized Brutalist Typography**: Space Grotesk for headers
- **Strict Monospace**: IBM Plex Mono / JetBrains Mono for cryptographic data
- **Animated Background**: Subtle data grid + particulate fog for depth

## Technology Stack

- **Framework**: Next.js 14 (App Router)
- **Styling**: Tailwind CSS 3.4 with custom Gilded Noir theme
- **UI Components**: shadcn/ui with custom variants
- **Animation**: Framer Motion 10
- **Icons**: Lucide React
- **Language**: TypeScript 5.3
- **Linting**: ESLint with Next.js config

## Project Structure

```
frontend/
├── app/                     # Next.js App Router
│   ├── layout.tsx          # Root layout with metadata
│   ├── page.tsx            # Home page showcase
│   └── globals.css         # Global styles + animations
├── components/
│   ├── ui/                 # shadcn/ui components (Button, Card)
│   └── ...                 # Feature components (TBD)
├── lib/
│   └── utils.ts            # Utility functions (cn())
├── tailwind.config.ts      # Gilded Noir theme configuration
├── tsconfig.json           # TypeScript strict mode config
├── next.config.ts          # Next.js optimization config
├── postcss.config.js       # PostCSS setup for Tailwind
└── components.json         # shadcn/ui configuration
```

## Getting Started

### Development

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

### Build for Production

```bash
npm run build
npm start
```

### Type Checking

```bash
npm run type-check
```

### Linting

```bash
npm run lint
```

## Gilded Noir Theme Highlights

### Color System

Custom colors defined in `tailwind.config.ts`:

- **`noir` palette**: Deep black to subtle gray hierarchy
- **`accent` palette**: Amber, cyan, emerald for status indicators
- **`glow` shadows**: Neon effects for interactive elements

### Typography

- **Headers** (`h1–h6`): Space Grotesk, oversized, uppercase, brutalist
- **Body**: Inter, strict line-height, accessible contrast
- **Code**: IBM Plex Mono, neon cyan, `.font-mono-strict`

### Animations

- **`data-grid`**: 20s linear scroll of horizontal lines (depth)
- **`fog-drift`**: 15s ease-in-out pulsing ambient fog
- **`glow-*`**: 2s ease-in-out neon glow effects (amber, cyan, emerald)
- **Respects**: `prefers-reduced-motion` for accessibility

### Accessibility

- **WCAG AA Compliance**: Minimum 91% contrast on text/background
- **Focus Indicators**: 2px cyan outline with 2px offset
- **High Contrast Mode**: Enhanced opacity for `prefers-contrast: more`
- **Keyboard Navigation**: All interactive elements are keyboard-accessible
- **Reduced Motion**: Animations disabled if `prefers-reduced-motion` is set

## Components

### `Button`

Neon accent buttons with variants:

```tsx
<Button variant="cyan" size="md">
  Secure Connection
</Button>
```

Variants: `default` | `amber` | `cyan` | `emerald` | `ghost`
Sizes: `sm` | `md` | `lg`

### `Card`

Bordered containers with neon glow on hover:

```tsx
<Card variant="cyan">
  <CardHeader>
    <CardTitle>Gateway Status</CardTitle>
  </CardHeader>
  <CardContent>Secure and operational</CardContent>
</Card>
```

Variants: `default` | `amber` | `cyan` | `emerald`

## Environment Variables

Create a `.env.local` file (copy from `.env.example`):

```env
NEXT_PUBLIC_GATEWAY_URL=http://localhost:8000/api/v1/gateway
NEXT_PUBLIC_HMAC_SECRET_KEY=your-256-bit-hex-key
NEXT_PUBLIC_ENV=development
NEXT_PUBLIC_DEBUG=false
```

## Next Steps

1. **Components Library**: Build out modular feature components (Dashboard, GatewayStatus, etc.)
2. **API Integration**: Wire frontend to backend gateway at `NEXT_PUBLIC_GATEWAY_URL`
3. **HMAC Client**: Implement client-side payload signing (matching backend crypto)
4. **Real-time Monitoring**: WebSocket or Server-Sent Events for gateway metrics
5. **Dark/Light Mode Toggle**: Theme switcher with persistent storage

## Performance

- **Image Optimization**: Next.js Image for automatic optimization
- **Font Loading**: `next/font` with `display: swap` for no layout shift
- **Code Splitting**: Automatic route-based code splitting
- **SWC Compilation**: Fast TypeScript → JavaScript transpilation

## Security

- **CSP Headers**: Content Security Policy (to be added)
- **XSS Prevention**: React's built-in escaping + strict TypeScript
- **CORS**: Configure for backend at `/api/v1/gateway`
- **No Secrets in Env**: `NEXT_PUBLIC_*` vars visible to browser only (no private keys)

## License

MIT
