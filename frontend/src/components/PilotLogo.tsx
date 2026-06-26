type PilotLogoProps = {
  variant?: 'mark' | 'full';
  className?: string;
};

export function PilotLogo({ variant = 'full', className = '' }: PilotLogoProps) {
  const size = variant === 'mark' ? 32 : 40;

  return (
    <div className={`flex items-center gap-2.5 ${className}`}>
      <img
        src="/assets/frappe_pilot/images/frappe-pilot-mark.svg"
        alt=""
        width={size}
        height={size}
        className="shrink-0"
        aria-hidden="true"
      />
      {variant === 'full' && (
        <div>
          <div className="text-base font-semibold text-pilot-700 leading-tight">Frappe Pilot</div>
          <div className="text-[11px] text-slate-500 leading-tight">AI assistant workspace</div>
        </div>
      )}
    </div>
  );
}
