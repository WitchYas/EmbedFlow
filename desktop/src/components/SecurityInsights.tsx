import React from 'react';
import { Shield, Package, AlertCircle } from 'lucide-react';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';

interface SecurityDataProps {
  cves: {
    critical: number;
    high: number;
    medium: number;
    low: number;
  };
  sbom: any[];
  layout?: "split" | "stack";
}

export const SecurityInsights: React.FC<SecurityDataProps> = ({ cves, sbom, layout = "split" }) => {
  const data = [
    { name: 'Critical', value: cves.critical, color: '#ef4444' },
    { name: 'High', value: cves.high, color: '#f97316' },
    { name: 'Medium', value: cves.medium, color: '#facc15' },
    { name: 'Low', value: cves.low, color: '#10b981' },
  ].filter(d => d.value > 0);

  const isStack = layout === "stack";

  return (
    <div className={`grid grid-cols-1 ${isStack ? "" : "md:grid-cols-2"} gap-6 mt-6 min-w-0`}>
      <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <Shield className="w-4 h-4 text-red-400" />
          <h3 className="text-sm font-semibold text-slate-200">Vulnerability Distribution</h3>
        </div>
        <div className="h-40 md:h-48">
          {data.length === 0 ? (
            <div className="h-full flex items-center justify-center text-xs text-slate-500 italic">
              No CVE data available
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={data}
                  innerRadius={isStack ? 48 : 60}
                  outerRadius={isStack ? 68 : 80}
                  paddingAngle={5}
                  dataKey="value"
                >
                  {data.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip 
                  contentStyle={{ backgroundColor: '#0f172a', border: 'none', borderRadius: '8px' }}
                  itemStyle={{ fontSize: '12px' }}
                />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>
        <div className="flex justify-center gap-4 flex-wrap mt-2">
          {data.map(d => (
            <div key={d.name} className="flex items-center gap-1.5">
              <div className="w-2 h-2 rounded-full" style={{ backgroundColor: d.color }} />
              <span className="text-[10px] text-slate-400 font-medium uppercase">{d.name}: {d.value}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <Package className="w-4 h-4 text-indigo-400" />
          <h3 className="text-sm font-semibold text-slate-200">Top Risk Packages (SBOM)</h3>
        </div>
        <div className="space-y-3 max-h-56 overflow-y-auto pr-2 custom-scrollbar">
          {sbom.slice(0, 10).map((pkg, idx) => (
            <div key={idx} className="flex items-center justify-between p-2 rounded-lg bg-slate-800/50 border border-slate-800/50">
              <div className="min-w-0">
                <p className="text-xs font-semibold text-slate-200 truncate">{pkg.package_name || pkg.package}</p>
                <p className="text-[10px] text-slate-500 font-mono">v{pkg.version}</p>
              </div>
              <div className="flex items-center gap-2">
                {pkg.highest_cvss > 7 && (
                  <AlertCircle className="w-3 h-3 text-red-500" />
                )}
                <span className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${
                  pkg.highest_cvss > 7 ? 'bg-red-500/10 text-red-500' : 'bg-slate-500/10 text-slate-500'
                }`}>
                  CVSS {pkg.highest_cvss || '0.0'}
                </span>
              </div>
            </div>
          ))}
          {sbom.length === 0 && (
            <p className="text-xs text-slate-500 italic text-center py-8">No data available</p>
          )}
        </div>
      </div>
    </div>
  );
};
