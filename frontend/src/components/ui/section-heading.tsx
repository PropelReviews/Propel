import * as React from "react";

import { cn } from "@/lib/utils";

// Heading + optional supporting copy for a marketing section. Centered by
// default; `align="left"` is used where the heading sits beside other content.
function SectionHeading({
  title,
  description,
  align = "center",
  className,
  ...props
}: Omit<React.ComponentProps<"div">, "title"> & {
  title: React.ReactNode;
  description?: React.ReactNode;
  align?: "center" | "left";
}) {
  return (
    <div
      data-slot="section-heading"
      className={cn(
        "max-w-2xl",
        align === "center" && "mx-auto text-center",
        className,
      )}
      {...props}
    >
      <h2 className="text-3xl font-semibold tracking-tight sm:text-4xl">{title}</h2>
      {description && (
        <p className="text-muted-foreground mt-4 text-lg">{description}</p>
      )}
    </div>
  );
}

export { SectionHeading };
