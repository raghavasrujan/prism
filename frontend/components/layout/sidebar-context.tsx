'use client';
import { createContext, useContext } from 'react';

type SidebarContextValue = {
  open: boolean;
  openSidebar: () => void;
  closeSidebar: () => void;
};

export const SidebarContext = createContext<SidebarContextValue>({
  open: true,
  openSidebar: () => {},
  closeSidebar: () => {},
});

export function useSidebar() {
  return useContext(SidebarContext);
}
