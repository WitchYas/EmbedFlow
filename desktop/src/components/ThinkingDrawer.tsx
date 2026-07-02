import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Brain, ChevronDown, ChevronUp, Sparkles, MessageSquare } from 'lucide-react';

interface ThinkingDrawerProps {
  thinking: string;
  adjustment: number;
  isOpen: boolean;
  onToggle: () => void;
}

export const ThinkingDrawer: React.FC<ThinkingDrawerProps> = ({ thinking, adjustment, isOpen, onToggle }) => {
  if (!thinking) return null;

  return (
    <div className="bg-amber-900/10 border border-amber-900/30 rounded-xl overflow-hidden mt-4">
      <button 
        onClick={onToggle}
        className="w-full flex items-center justify-between p-4 bg-amber-900/20 hover:bg-amber-900/30 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-amber-500/20 flex items-center justify-center">
            <Brain className="w-4 h-4 text-amber-500" />
          </div>
          <div className="text-left">
            <h4 className="text-sm font-semibold text-amber-200 flex items-center gap-2">
              DeepSeek-R1 Reflection Loop
              <Sparkles className="w-3 h-3 text-amber-400" />
            </h4>
            <p className="text-[10px] text-amber-400/70 font-mono uppercase tracking-widest">
              Confidence Adjustment: {adjustment > 0 ? '+' : ''}{adjustment}
            </p>
          </div>
        </div>
        {isOpen ? <ChevronUp className="w-4 h-4 text-amber-500" /> : <ChevronDown className="w-4 h-4 text-amber-500" />}
      </button>

      <AnimatePresence>
        {isOpen && (
          <motion.div 
            initial={{ height: 0 }}
            animate={{ height: "auto" }}
            exit={{ height: 0 }}
            className="overflow-hidden"
          >
            <div className="p-4 border-t border-amber-900/30 bg-black/40">
              <div className="flex items-start gap-3">
                <MessageSquare className="w-4 h-4 text-amber-600 mt-1 shrink-0" />
                <div className="text-xs text-amber-100/80 leading-relaxed font-mono whitespace-pre-wrap italic">
                  "{thinking}"
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
