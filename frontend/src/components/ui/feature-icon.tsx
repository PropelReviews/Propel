import * as React from "react"
import type { LucideIcon } from "lucide-react"

import { cn } from "@/lib/utils"

// Square, rounded icon tile used to head feature/option cards.
function FeatureIcon({
  icon: Icon,
  className,
  ...props
}: React.ComponentProps<"div"> & { icon: LucideIcon }) {
  return (
    <div
      data-slot="feature-icon"
      className={cn(
        "bg-muted text-foreground flex size-10 items-center justify-center rounded-lg",
        className,
      )}
      {...props}
    >
      <Icon className="size-5" />
    </div>
  )
}

export { FeatureIcon }
