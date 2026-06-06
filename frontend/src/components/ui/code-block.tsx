import * as React from "react"

import { cn } from "@/lib/utils"

// Read-only, preformatted code snippet (e.g. shell commands).
function CodeBlock({
  code,
  className,
  ...props
}: Omit<React.ComponentProps<"pre">, "children"> & { code: string }) {
  return (
    <pre
      data-slot="code-block"
      className={cn(
        "bg-muted/60 text-muted-foreground overflow-x-auto rounded-lg p-4 text-sm",
        className,
      )}
      {...props}
    >
      <code>{code}</code>
    </pre>
  )
}

export { CodeBlock }
