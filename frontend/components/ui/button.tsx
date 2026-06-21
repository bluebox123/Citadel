import * as React from "react";
import { cn } from "@/lib/utils";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "default" | "amber" | "cyan" | "emerald" | "ghost";
  size?: "sm" | "md" | "lg";
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant = "default",
      size = "md",
      ...props
    },
    ref
  ) => {
    const variantClasses = {
      default:
        "bg-noir-300 hover:bg-noir-400 text-white border border-accent-cyan-600 border-opacity-30 hover:shadow-glow-cyan hover:border-opacity-100",
      amber:
        "bg-accent-amber-500 hover:bg-accent-amber-400 text-noir-50 font-semibold hover:shadow-glow-amber",
      cyan:
        "bg-accent-cyan-500 hover:bg-accent-cyan-400 text-noir-50 font-semibold hover:shadow-glow-cyan",
      emerald:
        "bg-accent-emerald-500 hover:bg-accent-emerald-400 text-noir-50 font-semibold hover:shadow-glow-emerald",
      ghost:
        "hover:bg-noir-300 text-gray-300 hover:text-white border border-gray-600 border-opacity-50",
    };

    const sizeClasses = {
      sm: "px-3 py-1.5 text-sm",
      md: "px-4 py-2.5 text-base",
      lg: "px-6 py-3.5 text-lg",
    };

    return (
      <button
        className={cn(
          "inline-flex items-center justify-center gap-2 font-sans-brutalist font-bold uppercase tracking-wide rounded-lg transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed",
          variantClasses[variant],
          sizeClasses[size],
          className
        )}
        ref={ref}
        {...props}
      />
    );
  }
);

Button.displayName = "Button";

export { Button };
