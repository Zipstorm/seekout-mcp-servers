---
name: review-code
description: Reviews code against project coding guidelines and best practices. Use when reviewing code changes, checking for guideline violations, or improving existing code quality.
---

# Code Review

Use this skill to review code changes against the project's coding guidelines and best practices. Reference skill files that have related context to the changes made in this branch (e.g., React patterns, TypeScript rules, Tailwind styling, animations, effects). Skills are located in `.agents/skills/` (also symlinked at `.cursor/skills/`).

## Monorepo Scope

This review targets `apps/recruiter-ui`. When gathering changes and running checks, scope commands to that directory where possible. If a branch also touches files outside `apps/recruiter-ui`, note them but focus the skill-based review on the recruiter-ui code.

## Important: Skill-Based Reviews Only

**When reviewing code, if you are suggesting a useEffect make sure it doesn't violate the rules in the skill `.agents/skills/using-useEffects/SKILL.md`**

- Do: Suggest a useEffect if it is in best practices to do so
- Do: Let the user know when a useEffect they have is not following best practices
- Don't: Suggest a useEffect when it is not in best practices to do so

## Getting Branch Changes

Before reviewing, gather all changes on the current branch using these git commands:

### 1. Identify the current branch and base branch

```bash
git branch --show-current

git fetch origin
```

### 2. List all changed files on the branch

```bash
# List files changed compared to main branch
git diff --name-only origin/main...HEAD

# Or with status indicators (A=added, M=modified, D=deleted)
git diff --name-status origin/main...HEAD
```

### 3. View the full diff of all changes

```bash
# Full diff of all changes on the branch
git diff origin/main...HEAD

# Diff for TypeScript/React files only
git diff origin/main...HEAD -- '*.ts' '*.tsx'

# Diff scoped to recruiter-ui only
git diff origin/main...HEAD -- 'apps/recruiter-ui/'
```

### 4. Review commit history on the branch

```bash
# List commits on this branch not in main
git log origin/main..HEAD --oneline

# With more detail including changed files
git log origin/main..HEAD --stat
```

### 5. Read the changed files

After identifying changed files, read each one to perform the review.

**Note**: If the base branch is not `main`, replace `origin/main` with the appropriate base branch (e.g., `origin/develop`).

## Review Checklist

Build a checklist dynamically based on the changes in this branch:

### 1. Run TypeScript Check

Always run type checking first (changes to one file can cause errors in dependent files):

```bash
cd apps/recruiter-ui && pnpm exec tsc --noEmit
```

If errors are found, fix each type error and re-run until all are resolved.

### 2. Find Relevant Skills

Based on the file types and patterns in the changed code, identify which skill files apply. Prioritize the **recruiter-ui skill allowlist** defined in `apps/recruiter-ui/AGENTS.md`:

- **TypeScript/JavaScript files**: `typescript-type-safety`, `javascript-async-await`, `async-parallel`
- **React components (`.tsx`)**: `react-component-structure`, `react-jsx-patterns`, `using-useEffects`, `rerender-dependencies`, `rerender-defer-reads`, `rerender-lazy-state-init`, `rerender-transitions`
- **Styling changes**: `tailwind-styling`, `dark-mode`
- **Animations**: `rendering-animate-svg-wrapper`, `rendering-svg-precision`, `rendering-conditional-render`, `rendering-content-visibility`
- **API/data fetching**: `creating-swr-hooks`, `client-swr-dedup`
- **Bundle/performance**: `bundle-barrel-imports`, `bundle-conditional`, `bundle-preload`
- **Charts**: `echarts-tree-shaking`
- **Hooks (advanced)**: `advanced-event-handler-refs`, `advanced-use-latest`
- **Test files**: `testing-requirements`, `vitest-component-testing`

List the skills folder and read the relevant skill files to understand the guidelines.

### 3. Build the Checklist

For each relevant skill, create a checklist section using this format:

```markdown
### [Skill Topic Name]

- [ ] [Rule or guideline from the skill's Do's section]
- [ ] [Another rule - phrased as what the code SHOULD do]
- [ ] [Continue for each key rule in the skill]
```

**Example** (if reviewing React component changes):

```markdown
### React Component Structure

- [ ] Uses functional components (no class-based components)
- [ ] One component per file
- [ ] No `useMemo`, `useCallback`, or `React.memo` (React Compiler handles memoization)

### React JSX Patterns

- [ ] Uses ternaries (`? :`) instead of `&&` for conditional rendering
- [ ] Event props named `on{Event}`, handlers named `handle{Event}`
- [ ] Does not pass `setState` as props (uses event handler props instead)
```

### 4. Review Against Checklist

Go through each checklist item and verify the changed code follows the guideline. Mark items as checked or note violations.

## How to Use

1. Get the branch changes using the git commands above
2. Run TypeScript check (`cd apps/recruiter-ui && pnpm exec tsc --noEmit`)
3. Identify which skills are relevant based on the changed files
4. Read those skill files and build a checklist
5. Review each changed file against the checklist
6. For each violation found:
   - Identify the specific guideline being violated
   - Provide the corrected code following the "Do" examples from the skill file
7. Prioritize fixes by impact:
   - **High**: Type safety issues, unnecessary Effects, incorrect data fetching patterns
   - **Medium**: Event handling patterns, component structure
   - **Low**: Naming conventions, styling preferences

## Example Review Output

When reporting issues, use this format:

```
### Issue: [Brief description]

**Skill**: [Name of skill file, e.g., react-jsx-patterns]
**Rule**: [Specific rule being violated]

**Current code**:
```tsx
// problematic code
```

**Suggested fix**:
```tsx
// corrected code following the skill's Do example
```
```

## Quick Reference

| Pattern | Avoid | Prefer |
|---------|-------|--------|
| Async operations | `.then()/.catch()` | `async`/`await` |
| Conditional rendering | `{condition && <Component />}` | `{condition ? <Component /> : null}` |
| State setters as props | `<Child setFoo={setFoo} />` | `<Child onFooChange={handleFooChange} />` |
| Calculated values | `useEffect` + `useState` | Direct calculation during render |
| Data fetching | `useEffect` + `fetch` | `useSwrImmutable` / `useSwrMutation` |
| Expensive calculations | `useEffect` | Calculate during render |
| Memoization | `useMemo` / `useCallback` | Let React Compiler handle it |
| Colors | `bg-[#hex]` | `bg-(--palette-color)` |
| Spacing | `mb-2`, `px-4` | `mb-[8px]`, `px-[16px]` |
| Conditional classes | Template literals | `cn()` utility function |
| Component styles | CSS modules | Tailwind CSS |
| Style overrides | `!important` | Specificity / `cn(defaults, className)` |
| Layout | Grid (by default) | Flexbox (unless grid is clearer) |
| Components per file | Multiple components | 1 component per file |
| Transitions | `transition-all` | `transition-opacity`, `transition-transform` |
| Animatable properties | `top`, `left`, `width` | `opacity`, `transform` |
| Easing | `ease-in-*`, `ease` | `ease-out-*`, `ease-in-out-*` |
| Framer Motion components | `motion.div` | `m.div` with `LazyMotion` |
| Framer Motion transforms | `animate={{ x: 100 }}` | `style={{ transform: "translateX(100px)" }}` |
| New dependencies | Adding without asking | Get approval first |
| File naming (components) | `myComponent.tsx` | `MyComponent.tsx` (PascalCase) |
| File naming (hooks) | `UseHook.ts` | `useHook.ts` (camelCase with `use` prefix) |
| File naming (types) | `MyTypes.ts` | `my-types.types.ts` (kebab-case `.types.ts`) |
