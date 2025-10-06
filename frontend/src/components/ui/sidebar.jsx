import { cn } from "@/lib/utils";
import { Link, useLocation } from "react-router-dom";
import React, { useState, createContext, useContext } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { 
  X,
  LayoutDashboard,
  MessageSquare,
  FileText,
  Clock,
  CheckCircle,
  Upload,
  Database,
  LogOut,
  GitBranch,
} from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

const SidebarContext = createContext(undefined);

export const useSidebar = () => {
  const context = useContext(SidebarContext);
  if (!context) {
    throw new Error("useSidebar must be used within a SidebarProvider");
  }
  return context;
};

export const SidebarProvider = ({
  children,
  open: openProp,
  setOpen: setOpenProp,
  animate = true,
}) => {
  const [openState, setOpenState] = useState(false);

  const open = openProp !== undefined ? openProp : openState;
  const setOpen = setOpenProp !== undefined ? setOpenProp : setOpenState;

  return (
    <SidebarContext.Provider value={{ open, setOpen, animate }}>
      {children}
    </SidebarContext.Provider>
  );
};

export const SidebarWrapper = ({
  children,
  open,
  setOpen,
  animate,
}) => {
  return (
    <SidebarProvider open={open} setOpen={setOpen} animate={animate}>
      {children}
    </SidebarProvider>
  );
};

export const SidebarBody = (props) => {
  return (
    <>
      <DesktopSidebar {...props} />
      <MobileSidebar {...props} />
    </>
  );
};

export const DesktopSidebar = ({
  className,
  children,
  ...props
}) => {
  const { open, setOpen, animate } = useSidebar();
  return (
    <motion.div
      className={cn(
        "h-full px-4 py-4 hidden md:flex md:flex-col bg-neutral-100 w-[300px] flex-shrink-0",
        className
      )}
      animate={{
        width: animate ? (open ? "300px" : "60px") : "300px",
      }}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      {...props}
    >
      {children}
    </motion.div>
  );
};

export const MobileSidebar = ({
  className,
  children,
  ...props
}) => {
  const { open, setOpen } = useSidebar();
  return (
    <>
      <div
        className={cn(
          "h-16 px-4 flex flex-row md:hidden items-center justify-between bg-white w-full"
        )}
        {...props}
      >
        <div className="flex justify-start z-20 w-full">
          <button
            className="flex flex-col gap-1.5 cursor-pointer bg-transparent"
            onClick={() => setOpen(!open)}
            aria-label="Toggle menu"
          >
            <span className="w-6 h-0.5 bg-neutral-800 rounded-full"></span>
            <span className="w-6 h-0.5 bg-neutral-800 rounded-full"></span>
          </button>
        </div>
        <AnimatePresence>
          {open && (
            <motion.div
              initial={{ x: "-100%", opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              exit={{ x: "-100%", opacity: 0 }}
              transition={{
                duration: 0.3,
                ease: "easeInOut",
              }}
              className={cn(
                "fixed h-full w-full inset-0 bg-neutral-100 p-6 z-[100] flex flex-col justify-between",
                className
              )}
            >
              <div
                className="absolute right-6 top-6 z-50 text-neutral-800 cursor-pointer"
                onClick={() => setOpen(!open)}
              >
                <X />
              </div>
              {children}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </>
  );
};

export const SidebarLink = ({
  link,
  className,
  isActive,
  ...props
}) => {
  const { open, animate, setOpen } = useSidebar();
  return (
    <Link
      to={link.href}
      onClick={() => setOpen(false)}
      className={cn(
        "flex items-center justify-start gap-2 group/sidebar py-2 px-2 rounded-md transition hover:bg-neutral-200",
        isActive && "text-neutral-800",
        className
      )}
      {...props}
    >
      {link.icon}
      <motion.span
        animate={{
          display: animate ? (open ? "inline-block" : "none") : "inline-block",
          opacity: animate ? (open ? 1 : 0) : 1,
        }}
        className="text-neutral-700 text-sm group-hover/sidebar:translate-x-1 transition duration-150 whitespace-pre inline-block !p-0 !m-0"
      >
        {link.label}
      </motion.span>
    </Link>
  );
};

export function Sidebar() {
  const [open, setOpen] = useState(false);
  const location = useLocation();
  const { user, logout } = useAuth();
  
  const pathname = location.pathname;

  // Get user initials
  const getUserInitials = () => {
    if (!user?.full_name) return user?.email?.substring(0, 2).toUpperCase() || "U";
    const names = user.full_name.split(" ");
    return names.length > 1 
      ? `${names[0][0]}${names[1][0]}`.toUpperCase()
      : names[0].substring(0, 2).toUpperCase();
  };

  const isAdmin = user?.role === "admin";

  // Customer links
  const customerLinks = [
    {
      label: "Dashboard",
      href: "/",
      icon: <LayoutDashboard className="text-neutral-700 h-5 w-5 flex-shrink-0" />,
    },
    {
      label: "My Enquiries",
      href: "/enquiries",
      icon: <MessageSquare className="text-neutral-700 h-5 w-5 flex-shrink-0" />,
    },
    {
      label: "My Quotes",
      href: "/quotes",
      icon: <FileText className="text-neutral-700 h-5 w-5 flex-shrink-0" />,
    },
  ];

  // Admin links
  const adminLinks = [
    {
      label: "Pending Quotes",
      href: "/admin/pending",
      icon: <Clock className="text-neutral-700 h-5 w-5 flex-shrink-0" />,
    },
    {
      label: "Approved Quotes",
      href: "/admin/approved",
      icon: <CheckCircle className="text-neutral-700 h-5 w-5 flex-shrink-0" />,
    },
    {
      label: "Documents",
      href: "/admin/documents",
      icon: <Upload className="text-neutral-700 h-5 w-5 flex-shrink-0" />,
    },
    {
      label: "Knowledge Base",
      href: "/admin/knowledge-base",
      icon: <Database className="text-neutral-700 h-5 w-5 flex-shrink-0" />,
    },
    {
      label: "Decision Trees",
      href: "/admin/decision-trees",
      icon: <GitBranch className="text-neutral-700 h-5 w-5 flex-shrink-0" />,
    },
  ];

  return (
    <SidebarWrapper open={open} setOpen={setOpen}>
      <SidebarBody className="justify-between gap-10">
        <div className="flex flex-col flex-1 overflow-y-auto overflow-x-hidden">
          {open ? <Logo /> : <LogoIcon />}
          <div className="mt-8 flex flex-col gap-2">
            {customerLinks.map((link, idx) => (
              <SidebarLink 
                key={idx} 
                link={link}
                isActive={link.href === "/" ? pathname === "/" : pathname?.includes(link.href)}
              />
            ))}
            
            {/* Admin Routes */}
            {isAdmin && (
              <>
                <Separator className="w-full my-2" />
                {adminLinks.map((link, idx) => (
                  <SidebarLink 
                    key={`admin-${idx}`} 
                    link={link}
                    isActive={pathname?.includes(link.href)}
                  />
                ))}
              </>
            )}
          </div>
        </div>
        
        <div>
          <UserDropdown 
            user={user}
            isAdmin={isAdmin}
            logout={logout}
            open={open}
          />
        </div>
      </SidebarBody>
    </SidebarWrapper>
  );
}

const Logo = () => {
  return (
    <Link
      to="/"
      className="font-normal flex space-x-2 items-center text-sm text-black py-1 relative z-20"
    >
      <div className="h-5 w-6 bg-black rounded-br-lg rounded-tr-sm rounded-tl-lg rounded-bl-sm flex-shrink-0" />
      <motion.span
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="font-medium text-black whitespace-pre"
      >
        Ezzogenics
      </motion.span>
    </Link>
  );
};

const LogoIcon = () => {
  return (
    <Link
      to="/"
      className="font-normal flex space-x-2 items-center text-sm text-black py-1 relative z-20"
    >
      <div className="h-5 w-6 bg-black rounded-br-lg rounded-tr-sm rounded-tl-lg rounded-bl-sm flex-shrink-0" />
    </Link>
  );
};

const UserDropdown = ({ user, isAdmin, logout, open: sidebarOpen }) => {
  const { open, animate } = useSidebar();
  
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <div className="flex items-center justify-start gap-2 group/sidebar py-2 cursor-pointer hover:bg-neutral-200 rounded-md px-2">
          <div className="h-7 w-7 flex-shrink-0 rounded-full bg-neutral-300 flex items-center justify-center">
            <span className="text-neutral-700 text-xs font-medium">E</span>
          </div>
          <motion.span
            animate={{
              display: animate ? (open ? "inline-block" : "none") : "inline-block",
              opacity: animate ? (open ? 1 : 0) : 1,
            }}
            className="text-neutral-700 text-sm group-hover/sidebar:translate-x-1 transition duration-150 whitespace-pre inline-block !p-0 !m-0"
          >
            {user?.full_name || user?.email || "User"}
          </motion.span>
        </div>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-48">
        <div className="px-2 py-1.5 text-sm font-semibold">
          {user?.full_name || "User"}
        </div>
        <div className="px-2 py-1.5 text-xs text-neutral-500">
          {user?.email}
        </div>
        {isAdmin && (
          <div className="px-2 py-1">
            <Badge variant="secondary" className="text-xs">Admin</Badge>
          </div>
        )}
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={logout} className="cursor-pointer">
          <LogOut className="mr-2 h-4 w-4" />
          Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
};
