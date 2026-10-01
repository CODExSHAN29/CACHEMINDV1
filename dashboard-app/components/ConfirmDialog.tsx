"use client";
import { ReactNode, useEffect, useRef } from "react";
export default function ConfirmDialog({ title, children, onClose }: { title: string; children: ReactNode; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => { const node = dialog.current; node?.showModal(); return () => { node?.close(); }; }, []);
  return <dialog ref={dialog} onCancel={onClose} className="secret-dialog text-on-surface backdrop:bg-black/80" aria-label={title}><h2 className="section-index">{title}</h2>{children}</dialog>;
}
