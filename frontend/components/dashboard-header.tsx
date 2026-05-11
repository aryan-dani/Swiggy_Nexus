"use client";

import { Bell, Menu, Search, Settings } from "lucide-react";
import Link from "next/link";
import * as React from "react";
import { motion } from "framer-motion";

import { AppSidebar, type AppSidebarProps } from "@/components/app-sidebar";
import {
  Sheet,
  SheetContent,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { fadeIn, fadeUp, neoSpring, staggerContainer } from "@/lib/motion";
import { nexusToast } from "@/lib/nexus-toast-bus";
import { cn } from "@/lib/utils";

const MotionLink = motion.create(Link);

export type DashboardHeaderProps = {
  sidebarProps: AppSidebarProps;
  className?: string;
};

export function DashboardHeader({
  sidebarProps,
  className,
}: DashboardHeaderProps) {
  const [open, setOpen] = React.useState(false);

  return (
    <motion.header
      initial={{ y: -16, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={neoSpring}
      className={cn(
        "sticky top-0 z-30 flex h-20 shrink-0 items-center justify-between gap-4 border-b-2 border-black bg-white px-4 md:px-8",
        className
      )}
    >
      <motion.div
        className="flex min-w-0 flex-1 items-center gap-3 md:gap-4"
        variants={staggerContainer}
        initial="hidden"
        animate="show"
      >
        <motion.div variants={fadeUp}>
          <Sheet open={open} onOpenChange={setOpen}>
            <SheetTrigger asChild>
              <motion.button
                type="button"
                whileHover={{ scale: 1.04 }}
                whileTap={{ scale: 0.96 }}
                className="flex h-10 w-10 items-center justify-center border-2 border-black bg-white shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] md:hidden"
                aria-label="Open menu"
              >
                <Menu className="h-5 w-5 text-black" />
              </motion.button>
            </SheetTrigger>
            <SheetContent
              side="left"
              className="flex w-[min(100vw-1rem,20rem)] flex-col overflow-x-hidden border-2 border-black bg-white p-6 pr-7"
            >
              <SheetTitle className="sr-only">Navigation</SheetTitle>
              <AppSidebar
                {...sidebarProps}
                className="h-full"
                onNavigate={(tab?: string) => {
                  setOpen(false);
                  if (tab && sidebarProps.onNavigate) {
                    sidebarProps.onNavigate(tab);
                  }
                }}
              />
            </SheetContent>
          </Sheet>
        </motion.div>

        <motion.div
          variants={fadeUp}
          className="relative hidden w-80 max-w-full group md:block"
        >
          <Search
            className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
            aria-hidden
          />
          <motion.input
            whileFocus={{
              boxShadow: "3px 3px 0px 0px rgba(0,0,0,1)",
              scale: 1.01,
            }}
            transition={{ type: "spring", stiffness: 450, damping: 28 }}
            className="w-full border-2 border-black bg-slate-50 py-2 pl-9 pr-4 font-display text-sm font-medium text-black placeholder:text-slate-500 focus:outline-none"
            placeholder="Search sessions..."
            type="search"
            aria-label="Search sessions"
          />
        </motion.div>

        <motion.span
          variants={fadeIn}
          className="font-display text-sm font-black text-black md:hidden"
        >
          Nexus
        </motion.span>
      </motion.div>

      <motion.div
        className="flex items-center gap-2 md:gap-4"
        variants={staggerContainer}
        initial="hidden"
        animate="show"
      >
        <motion.button
          type="button"
          variants={fadeUp}
          whileHover={{
            scale: 1.06,
            boxShadow: "4px 4px 0px 0px rgba(0,0,0,1)",
            transition: neoSpring,
          }}
          whileTap={{
            scale: 0.97,
            boxShadow: "2px 2px 0px 0px rgba(0,0,0,1)",
            transition: neoSpring,
          }}
          className="flex h-10 w-10 items-center justify-center border-2 border-black bg-white shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]"
          aria-label="Notifications"
          onClick={() =>
            nexusToast("No new notifications — demo inbox is quiet.")
          }
        >
          <Bell size={18} className="text-black" />
        </motion.button>
        <MotionLink
          href="/settings"
          aria-label="Settings"
          variants={fadeUp}
          whileHover={{
            scale: 1.06,
            boxShadow: "4px 4px 0px 0px rgba(0,0,0,1)",
            transition: neoSpring,
          }}
          whileTap={{
            scale: 0.97,
            boxShadow: "2px 2px 0px 0px rgba(0,0,0,1)",
            transition: neoSpring,
          }}
          className="flex h-10 w-10 items-center justify-center border-2 border-black bg-white shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] transition-colors hover:bg-slate-50"
        >
          <Settings size={18} className="text-black" />
        </MotionLink>
        <motion.div variants={fadeUp} className="mx-1 hidden h-10 w-0.5 bg-black md:block" />
        <motion.button
          variants={fadeUp}
          type="button"
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.98 }}
          className="hidden h-12 w-12 overflow-hidden rounded-full border-2 border-black bg-slate-200 shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] md:block"
          aria-label="Profile"
        >
          <img
            alt=""
            className="h-full w-full object-cover"
            src="https://randomuser.me/api/portraits/men/32.jpg"
          />
        </motion.button>
      </motion.div>
    </motion.header>
  );
}
