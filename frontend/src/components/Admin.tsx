/**
 * Public-site (PUBLIC_MODE) helpers: a short note where an admin-only action is hidden, with an
 * optional admin sign-in (the token is kept in this browser only and sent as X-Admin-Token).
 */
import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { adminToken, setAdminToken, useAccess } from '../api/client'
import { HelpTip } from '../help'

/** Shown instead of an admin-only control on the public site. Renders nothing on a private install or for the admin. */
export function AdminOnlyNote({ what, className = '', signIn = true }: { what: string; className?: string; signIn?: boolean }) {
  const a = useAccess()
  if (!a.loaded || !a.publicMode || a.admin) return null
  return (
    <div className={`flex flex-wrap items-center gap-x-2 gap-y-1 text-[12px] text-ink-3 ${className}`}>
      <span className="inline-flex items-center gap-1">Public site: {what} is reserved for the site owner. <HelpTip id="public_mode" label="What is the public site?" /></span>
      {signIn && <AdminSignIn />}
    </div>
  )
}

/** Small "Owner sign-in" disclosure with a password field for the admin token. */
export function AdminSignIn({ className = '' }: { className?: string }) {
  const qc = useQueryClient()
  const a = useAccess()
  const [tok, setTok] = useState(adminToken)
  const [open, setOpen] = useState(false)
  const apply = (t: string) => {
    setAdminToken(t.trim())
    qc.invalidateQueries({ queryKey: ['access'] })
  }
  if (!a.publicMode) return null
  return (
    <span className={`inline-flex flex-wrap items-center gap-1.5 ${className}`}>
      {!open ? (
        <button type="button" className="link text-[12px]" onClick={() => setOpen(true)}>{a.admin ? 'Owner signed in' : 'Owner sign-in'}</button>
      ) : (
        <form className="inline-flex flex-wrap items-center gap-1.5" onSubmit={(e) => { e.preventDefault(); apply(tok); setOpen(false) }}>
          <label className="sr-only" htmlFor="admin-token">Admin token</label>
          <input id="admin-token" className="input w-40 !py-1 text-[12px]" type="password" autoComplete="off" placeholder="Admin token"
            value={tok} onChange={(e) => setTok(e.target.value)} />
          <button type="submit" className="btn !px-2 !py-1 !text-[12px]">Save</button>
          {tok && <button type="button" className="btn !px-2 !py-1 !text-[12px]" onClick={() => { setTok(''); apply(''); setOpen(false) }}>Sign out</button>}
        </form>
      )}
    </span>
  )
}
