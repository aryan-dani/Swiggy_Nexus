import Image from "next/image";

import { cn } from "@/lib/utils";

const BIRD = "/images/nexus-bird.png";

type NexusLogoMarkProps = {
  className?: string;
  "aria-label"?: string;
};

/** Bird mark inside a yellow neo frame; PNG sits on a light panel to match asset background. */
export function NexusLogoMark({
  className,
  "aria-label": ariaLabel = "Swiggy Nexus",
}: NexusLogoMarkProps) {
  return (
    <div
      role="img"
      aria-label={ariaLabel}
      className={cn(
        "box-border flex aspect-square shrink-0 flex-col border-2 border-black bg-neo-yellow p-1",
        className
      )}
    >
      <div className="relative flex min-h-0 flex-1 items-center justify-center bg-[#ececec]">
        <Image
          src={BIRD}
          alt=""
          width={160}
          height={160}
          className="max-h-[88%] max-w-[88%] object-contain"
          sizes="(max-width: 768px) 40px, 48px"
        />
      </div>
    </div>
  );
}

type NexusLockupProps = {
  className?: string;
};

/** Lockup: yellow bird tile + type stack on white (reference layout — no gray slab). */
export function NexusLockup({ className }: NexusLockupProps) {
  return (
    <div
      className={cn(
        "flex w-full min-w-0 items-center gap-3.5 text-left",
        className
      )}
    >
      <NexusLogoMark
        className="h-[4.25rem] w-[4.25rem] shrink-0 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]"
        aria-label="Swiggy Nexus"
      />
      <div className="min-w-0 flex-1 leading-tight">
        <p className="font-display text-lg font-black tracking-tight text-black sm:text-xl">
          Swiggy Nexus
        </p>
        <p className="mt-0.5 font-display text-[10px] font-bold uppercase tracking-[0.12em] text-slate-500 sm:text-[11px]">
          MOCK MCP - DEMO
        </p>
      </div>
    </div>
  );
}
