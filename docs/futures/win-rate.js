import {wilson} from './engine.js';
// Descriptive, expanding-window estimator. NEVER reads a still-open or later trade.
export function annotatePriorWinRates(run){for(const t of run.trades){const low=Math.min(90,Math.floor(t.score/10)*10),high=low===90?100:low+9,prior=run.trades.filter(p=>p.exitMinute<t.entryMinute&&p.score>=low&&p.score<=high),wins=prior.filter(p=>p.netPnl>0).length;
 t.empirical={bucket:[low,high],pastCompleted:prior.length,pastWins:wins,winRate:prior.length>=30?wins/prior.length:null,interval:prior.length>=30?wilson(wins,prior.length):null,status:prior.length>=30?'historical_frequency_not_guarantee':'fewer_than_30_prior_trades'};}
 return run;}
