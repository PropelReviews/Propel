import * as React from "react"

import { cn } from "@/lib/utils"

// Page section shell used across the marketing pages: a full-width <section>
// with an optional top border and a centered max-width content container.
function Section({
  className,
  containerClassName,
  bordered = true,
  children,
  ...props
}: React.ComponentProps<"section"> & {
  containerClassName?: string
  bordered?: boolean
}) {
  return (
    <section
      data-slot="section"
      className={cn(bordered && "border-t border-border/60", className)}
      {...props}
    >
      <div className={cn("mx-auto max-w-6xl px-6 py-24", containerClassName)}>
        {children}
      </div>
    </section>
  )
}

export { Section }
