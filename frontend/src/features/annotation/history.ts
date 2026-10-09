import type { Annotation } from '../../types';

export type History = { past: Annotation[][]; present: Annotation[]; future: Annotation[][] };
export type HistoryAction = { type: 'reset' | 'change'; objects: Annotation[] } | { type: 'undo' | 'redo' };
export function historyReducer(state: History, action: HistoryAction): History {
  switch (action.type) {
    case 'reset': return { past: [], present: action.objects, future: [] };
    case 'change':
      if (JSON.stringify(state.present) === JSON.stringify(action.objects)) return state;
      return { past: [...state.past.slice(-99), state.present], present: action.objects, future: [] };
    case 'undo': return state.past.length ? { past: state.past.slice(0, -1), present: state.past[state.past.length-1], future: [state.present, ...state.future] } : state;
    case 'redo': return state.future.length ? { past: [...state.past, state.present], present: state.future[0], future: state.future.slice(1) } : state;
  }
}
