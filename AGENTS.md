# Loom Design Context

## Design Context

### Users

**Primary Users**: Developers and DevOps teams building agentic systems
**Secondary Users**: Technical writers, AI/ML engineers, documentation teams

**User Context**:
- Building multi-agent workflow orchestration systems
- Configuring organizations, agents, and workflows
- Monitoring task execution and debugging issues
- Managing integrations (LiteLLM, OpenAI, OpenCode)

**Primary Job-to-be-Done**: Create and configure agents/workflows to orchestrate complex tasks

**User Mental Model**:
- Infrastructure-first mindset ("Control Plane")
- Values determinism, reliability, and visibility
- Needs quick access to configuration and monitoring
- Comfortable with technical interfaces

### Brand Personality

**Three Words**: Modern, Clean, Developer-friendly

**Tone**: Technical and precise, but approachable
- Professional without being stuffy
- Functional over decorative
- Clear and direct communication
- Values simplicity and efficiency

**Emotional Goals**:
- **Confidence**: Users should feel in control of complex systems
- **Clarity**: Interface should make orchestration understandable
- **Efficiency**: Minimize friction in configuration workflows

### Aesthetic Direction

**Visual Tone**: Modern developer tools aesthetic (like Vercel, Linear, GitHub)

**Color Strategy**:
- **Primary**: Warm amber (#f59e0b) — distinctive from typical teal/cyan AI tools
- **Neutrals**: Warm-tinted grays (0.01 chroma at 60° hue)
- **Status**: Semantic colors (green=success, yellow=warning, red=error, blue=info)
- **Dark Mode**: Never pure black, subtle warm tint even in darks

**Typography**:
- System font stack for performance
- Clean hierarchy with meaningful contrast
- Monospace for code/configurations

**Layout Principles**:
- Card-based organization (justified for admin dashboards)
- Consistent 8px spacing grid
- Clear visual hierarchy
- Left-aligned text (not centered)
- Generous white space

### Design Principles

1. **Accessibility First**: All features must work with keyboard navigation, screen readers, and meet WCAG AA (4.5:1 contrast minimum)

2. **Semantic HTML**: Use proper elements (`<button>`, `<nav>`, `<main>`, ARIA roles) for built-in accessibility

3. **Progressive Disclosure**: Show primary actions clearly, hide complexity behind clear entry points

4. **Consistent Interactions**: Every interactive element has all states (default, hover, focus, active, disabled, loading)

5. **Mobile-First Responsive**: Touch targets 44x44px minimum, works on all screen sizes

6. **OKLCH Color System**: Perceptually uniform colors, no pure black/gray, tinted neutrals

7. **Clear Feedback**: No `alert()` dialogs — inline notifications, loading states, success/error messages

8. **Simplify Without Stripping**: Remove obstacles, not functionality; streamline workflows

## Design Tokens

### Color Palette (OKLCH)

```css
/* Amber Primary */
--amber-500: oklch(66% 0.19 85);  /* Primary accent */
--amber-400: oklch(73% 0.16 85);  /* Hover state */
--amber-600: oklch(59% 0.18 85);  /* Active state */

/* Warm Neutrals */
--gray-50: oklch(97% 0.005 60);   /* Background */
--gray-100: oklch(93% 0.006 60);  /* Card backgrounds */
--gray-500: oklch(64% 0.009 60);  /* Muted text */
--gray-900: oklch(32% 0.007 60);  /* Dark backgrounds */
```

### Spacing Scale

- `4px` — Tight (internal padding)
- `8px` — Default gap
- `12px` — Card padding
- `16px` — Section gaps
- `20px` — Page padding
- `24px` — Large separations

### Typography Scale

- `0.75rem` — Captions, badges
- `0.85rem` — Secondary text, hints
- `0.9rem` — Buttons
- `1rem` — Body text
- `1.1rem` — Card titles
- `1.25rem` — View titles
- `1.5rem` — Brand/header

## Implementation Guidelines

### When Adding New Features

1. **Use semantic HTML** — `<button>` for actions, `<nav>` for navigation
2. **Include all states** — :hover, :focus-visible, :active, [disabled], [aria-busy]
3. **Touch targets** — Minimum 44x44px for interactive elements
4. **Color tokens** — Use semantic tokens, not hard-coded hex values
5. **Labels** — All inputs must have associated `<label>` or `aria-label`
6. **Error handling** — Use `showNotification()` not `alert()`
7. **Loading states** — Set `aria-busy="true"` and `disabled` during async operations
8. **Empty states** — Use `.empty-state` pattern with icon, title, and description

### Anti-Patterns to Avoid

- ❌ `alert()` for user feedback
- ❌ Missing form labels
- ❌ Inline styles
- ❌ Hard-coded hex colors
- ❌ Touch targets < 44px
- ❌ Non-semantic interactive elements
- ❌ Gray text on colored backgrounds
- ❌ Pure black (#000) or pure gray

## Browser Support

- Modern evergreen browsers (Chrome, Firefox, Safari, Edge)
- CSS Grid and Flexbox required
- OKLCH color support (fallbacks not currently implemented)
- Keyboard navigation required
- Screen reader compatibility (NVDA, JAWS, VoiceOver)

## Accessibility Requirements

**WCAG 2.1 AA Compliance**:
- 4.5:1 contrast ratio for normal text
- 3:1 contrast for large text and UI components
- Keyboard navigation for all functionality
- Focus indicators visible (3px solid outline)
- Skip link for main content
- ARIA labels where needed
- Reduced motion support (`prefers-reduced-motion`)

---

*Last updated: 2026-03-14*
*Designer: Open-Thinking Model*
