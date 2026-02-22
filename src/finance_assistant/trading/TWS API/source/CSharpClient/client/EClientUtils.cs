/* Copyright (C) 2025 Interactive Brokers LLC. All rights reserved. This code is subject to the terms
 * and conditions of the IB API Non-Commercial License or the IB API Commercial License, as applicable. */

using System.Collections.Generic;
using System.Linq;

namespace IBApi
{
    internal class EClientUtils
    {
	    public static protobuf.ExecutionRequest createExecutionRequestProto(int reqId, ExecutionFilter filter)
        {
            protobuf.ExecutionFilter executionFilterProto = new protobuf.ExecutionFilter();
            if (Util.IsValidValue(filter.ClientId)) executionFilterProto.ClientId = filter.ClientId;
            if (!Util.StringIsEmpty(filter.AcctCode)) executionFilterProto.AcctCode = filter.AcctCode;
            if (!Util.StringIsEmpty(filter.Time)) executionFilterProto.Time = filter.Time;
            if (!Util.StringIsEmpty(filter.Symbol)) executionFilterProto.Symbol = filter.Symbol;
            if (!Util.StringIsEmpty(filter.SecType)) executionFilterProto.SecType = filter.SecType;
            if (!Util.StringIsEmpty(filter.Exchange)) executionFilterProto.Exchange = filter.Exchange;
            if (!Util.StringIsEmpty(filter.Side)) executionFilterProto.Side = filter.Side;
            if (Util.IsValidValue(filter.LastNDays)) executionFilterProto.LastNDays = filter.LastNDays;
            if (filter.SpecificDates != null && filter.SpecificDates.Any()) executionFilterProto.SpecificDates.AddRange(filter.SpecificDates);

            protobuf.ExecutionRequest executionRequestProto = new protobuf.ExecutionRequest();
            if (Util.IsValidValue(reqId)) executionRequestProto.ReqId = reqId;
            executionRequestProto.ExecutionFilter = executionFilterProto;
                 
            return executionRequestProto;
        }

        public static protobuf.PlaceOrderRequest createPlaceOrderRequestProto(int orderId, Contract contract, Order order) 
        {
            protobuf.PlaceOrderRequest placeOrderRequestProto = new protobuf.PlaceOrderRequest();
            if (Util.IsValidValue(orderId)) placeOrderRequestProto.OrderId = orderId;

            protobuf.Contract contractProto = createContractProto(contract, order);
            if (contractProto != null) placeOrderRequestProto.Contract = contractProto;

            protobuf.Order orderProto = createOrderProto(order);
            if (orderProto != null) placeOrderRequestProto.Order = orderProto;

            return placeOrderRequestProto;
        }

        public static protobuf.Order createOrderProto(Order order) 
        {
            protobuf.Order orderProto = new protobuf.Order();
            if (Util.IsValidValue(order.ClientId)) orderProto.ClientId = order.ClientId;
            if (Util.IsValidValue(order.PermId)) orderProto.PermId = order.PermId;
            if (Util.IsValidValue(order.ParentId)) orderProto.ParentId = order.ParentId;
            if (!Util.StringIsEmpty(order.Action)) orderProto.Action = order.Action;
            if (Util.IsValidValue(order.TotalQuantity)) orderProto.TotalQuantity = order.TotalQuantity.ToString();
            if (Util.IsValidValue(order.DisplaySize)) orderProto.DisplaySize = order.DisplaySize;
            if (!Util.StringIsEmpty(order.OrderType)) orderProto.OrderType = order.OrderType;
            if (Util.IsValidValue(order.LmtPrice)) orderProto.LmtPrice = order.LmtPrice;
            if (Util.IsValidValue(order.AuxPrice)) orderProto.AuxPrice = order.AuxPrice;
            if (!Util.StringIsEmpty(order.Tif)) orderProto.Tif = order.Tif;
            if (!Util.StringIsEmpty(order.Account)) orderProto.Account = order.Account;
            if (!Util.StringIsEmpty(order.SettlingFirm)) orderProto.SettlingFirm = order.SettlingFirm;
            if (!Util.StringIsEmpty(order.ClearingAccount)) orderProto.ClearingAccount = order.ClearingAccount;
            if (!Util.StringIsEmpty(order.ClearingIntent)) orderProto.ClearingIntent = order.ClearingIntent;
            if (order.AllOrNone) orderProto.AllOrNone = order.AllOrNone;
            if (order.BlockOrder) orderProto.BlockOrder = order.BlockOrder;
            if (order.Hidden) orderProto.Hidden = order.Hidden;
            if (order.OutsideRth) orderProto.OutsideRth = order.OutsideRth;
            if (order.SweepToFill) orderProto.SweepToFill = order.SweepToFill;
            if (Util.IsValidValue(order.PercentOffset)) orderProto.PercentOffset = order.PercentOffset;
            if (Util.IsValidValue(order.TrailingPercent)) orderProto.TrailingPercent = order.TrailingPercent;
            if (Util.IsValidValue(order.TrailStopPrice)) orderProto.TrailStopPrice = order.TrailStopPrice;
            if (Util.IsValidValue(order.MinQty)) orderProto.MinQty = order.MinQty;
            if (!Util.StringIsEmpty(order.GoodAfterTime)) orderProto.GoodAfterTime = order.GoodAfterTime;
            if (!Util.StringIsEmpty(order.GoodTillDate)) orderProto.GoodTillDate = order.GoodTillDate;
            if (!Util.StringIsEmpty(order.OcaGroup)) orderProto.OcaGroup = order.OcaGroup;
            if (!Util.StringIsEmpty(order.OrderRef)) orderProto.OrderRef = order.OrderRef;
            if (!Util.StringIsEmpty(order.Rule80A)) orderProto.Rule80A = order.Rule80A;
            if (Util.IsValidValue(order.OcaType)) orderProto.OcaType = order.OcaType;
            if (Util.IsValidValue(order.TriggerMethod)) orderProto.TriggerMethod = order.TriggerMethod;
            if (!Util.StringIsEmpty(order.ActiveStartTime)) orderProto.ActiveStartTime = order.ActiveStartTime;
            if (!Util.StringIsEmpty(order.ActiveStopTime)) orderProto.ActiveStopTime = order.ActiveStopTime;
            if (!Util.StringIsEmpty(order.FaGroup)) orderProto.FaGroup = order.FaGroup;
            if (!Util.StringIsEmpty(order.FaMethod)) orderProto.FaMethod = order.FaMethod;
            if (!Util.StringIsEmpty(order.FaPercentage)) orderProto.FaPercentage = order.FaPercentage;
            if (Util.IsValidValue(order.Volatility)) orderProto.Volatility = order.Volatility;
            if (Util.IsValidValue(order.VolatilityType)) orderProto.VolatilityType = order.VolatilityType;
            if (Util.IsValidValue(order.ContinuousUpdate)) orderProto.ContinuousUpdate = order.ContinuousUpdate == 1;
            if (Util.IsValidValue(order.ReferencePriceType)) orderProto.ReferencePriceType = order.ReferencePriceType;
            if (!Util.StringIsEmpty(order.DeltaNeutralOrderType)) orderProto.DeltaNeutralOrderType = order.DeltaNeutralOrderType;
            if (Util.IsValidValue(order.DeltaNeutralAuxPrice)) orderProto.DeltaNeutralAuxPrice = order.DeltaNeutralAuxPrice;
            if (Util.IsValidValue(order.DeltaNeutralConId)) orderProto.DeltaNeutralConId = order.DeltaNeutralConId;
            if (!Util.StringIsEmpty(order.DeltaNeutralOpenClose)) orderProto.DeltaNeutralOpenClose = order.DeltaNeutralOpenClose;
            if (order.DeltaNeutralShortSale) orderProto.DeltaNeutralShortSale = order.DeltaNeutralShortSale;
            if (Util.IsValidValue(order.DeltaNeutralShortSaleSlot)) orderProto.DeltaNeutralShortSaleSlot = order.DeltaNeutralShortSaleSlot;
            if (!Util.StringIsEmpty(order.DeltaNeutralDesignatedLocation)) orderProto.DeltaNeutralDesignatedLocation = order.DeltaNeutralDesignatedLocation;
            if (Util.IsValidValue(order.ScaleInitLevelSize)) orderProto.ScaleInitLevelSize = order.ScaleInitLevelSize;
            if (Util.IsValidValue(order.ScaleSubsLevelSize)) orderProto.ScaleSubsLevelSize = order.ScaleSubsLevelSize;
            if (Util.IsValidValue(order.ScalePriceIncrement)) orderProto.ScalePriceIncrement = order.ScalePriceIncrement;
            if (Util.IsValidValue(order.ScalePriceAdjustValue)) orderProto.ScalePriceAdjustValue = order.ScalePriceAdjustValue;
            if (Util.IsValidValue(order.ScalePriceAdjustInterval)) orderProto.ScalePriceAdjustInterval = order.ScalePriceAdjustInterval;
            if (Util.IsValidValue(order.ScaleProfitOffset)) orderProto.ScaleProfitOffset = order.ScaleProfitOffset;
            if (order.ScaleAutoReset) orderProto.ScaleAutoReset = order.ScaleAutoReset;
            if (Util.IsValidValue(order.ScaleInitPosition)) orderProto.ScaleInitPosition = order.ScaleInitPosition;
            if (Util.IsValidValue(order.ScaleInitFillQty)) orderProto.ScaleInitFillQty = order.ScaleInitFillQty;
            if (order.ScaleRandomPercent) orderProto.ScaleRandomPercent = order.ScaleRandomPercent;
            if (!Util.StringIsEmpty(order.ScaleTable)) orderProto.ScaleTable = order.ScaleTable;
            if (!Util.StringIsEmpty(order.HedgeType)) orderProto.HedgeType = order.HedgeType;
            if (!Util.StringIsEmpty(order.HedgeParam)) orderProto.HedgeParam = order.HedgeParam;

	        if (!Util.StringIsEmpty(order.AlgoStrategy)) orderProto.AlgoStrategy = order.AlgoStrategy;
            if (order.AlgoParams != null && order.AlgoParams.Any())
            {
                Dictionary<string, string> algoParams = order.AlgoParams.ToDictionary(tagValue => tagValue.Tag, tagValue => tagValue.Value);
                orderProto.AlgoParams.Add(algoParams);
            }
            if (!Util.StringIsEmpty(order.AlgoId)) orderProto.AlgoId = order.AlgoId;

            if (order.SmartComboRoutingParams != null && order.SmartComboRoutingParams.Any())
            {
                Dictionary<string, string> smartComboRoutingParams = order.SmartComboRoutingParams.ToDictionary(tagValue => tagValue.Tag, tagValue => tagValue.Value);
                orderProto.SmartComboRoutingParams.Add(smartComboRoutingParams);
            }

            if (order.WhatIf) orderProto.WhatIf = order.WhatIf;
            if (order.Transmit) orderProto.Transmit = order.Transmit;
            if (order.OverridePercentageConstraints) orderProto.OverridePercentageConstraints = order.OverridePercentageConstraints;
            if (!Util.StringIsEmpty(order.OpenClose)) orderProto.OpenClose = order.OpenClose;
            if (Util.IsValidValue(order.Origin)) orderProto.Origin = order.Origin;
            if (Util.IsValidValue(order.ShortSaleSlot)) orderProto.ShortSaleSlot = order.ShortSaleSlot;
            if (!Util.StringIsEmpty(order.DesignatedLocation)) orderProto.DesignatedLocation = order.DesignatedLocation;
            if (Util.IsValidValue(order.ExemptCode)) orderProto.ExemptCode = order.ExemptCode;
            if (!Util.StringIsEmpty(order.DeltaNeutralSettlingFirm)) orderProto.DeltaNeutralSettlingFirm = order.DeltaNeutralSettlingFirm;
            if (!Util.StringIsEmpty(order.DeltaNeutralClearingAccount)) orderProto.DeltaNeutralClearingAccount = order.DeltaNeutralClearingAccount;
            if (!Util.StringIsEmpty(order.DeltaNeutralClearingIntent)) orderProto.DeltaNeutralClearingIntent = order.DeltaNeutralClearingIntent;
            if (Util.IsValidValue(order.DiscretionaryAmt)) orderProto.DiscretionaryAmt = order.DiscretionaryAmt;
            if (order.OptOutSmartRouting) orderProto.OptOutSmartRouting = order.OptOutSmartRouting;
            if (Util.IsValidValue(order.ExemptCode)) orderProto.ExemptCode = order.ExemptCode;
            if (Util.IsValidValue(order.StartingPrice)) orderProto.StartingPrice = order.StartingPrice;
            if (Util.IsValidValue(order.StockRefPrice)) orderProto.StockRefPrice = order.StockRefPrice;
            if (Util.IsValidValue(order.Delta)) orderProto.Delta = order.Delta;
            if (Util.IsValidValue(order.StockRangeLower)) orderProto.StockRangeLower = order.StockRangeLower;
            if (Util.IsValidValue(order.StockRangeUpper)) orderProto.StockRangeUpper = order.StockRangeUpper;
            if (order.NotHeld) orderProto.NotHeld = order.NotHeld;

            if (order.OrderMiscOptions != null && order.OrderMiscOptions.Any())
            {
                Dictionary<string, string> orderMiscOptions = order.OrderMiscOptions.ToDictionary(tagValue => tagValue.Tag, tagValue => tagValue.Value);
                orderProto.OrderMiscOptions.Add(orderMiscOptions);
            }

            if (order.Solicited) orderProto.Solicited = order.Solicited;
            if (order.RandomizeSize) orderProto.RandomizeSize = order.RandomizeSize;
            if (order.RandomizePrice) orderProto.RandomizePrice = order.RandomizePrice;
            if (Util.IsValidValue(order.ReferenceContractId)) orderProto.ReferenceContractId = order.ReferenceContractId;
            if (Util.IsValidValue(order.PeggedChangeAmount)) orderProto.PeggedChangeAmount = order.PeggedChangeAmount;
            if (order.IsPeggedChangeAmountDecrease) orderProto.IsPeggedChangeAmountDecrease = order.IsPeggedChangeAmountDecrease;
            if (Util.IsValidValue(order.ReferenceChangeAmount)) orderProto.ReferenceChangeAmount = order.ReferenceChangeAmount;
            if (!Util.StringIsEmpty(order.ReferenceExchange)) orderProto.ReferenceExchangeId = order.ReferenceExchange;

            if (order.AdjustedOrderType != null && !Util.StringIsEmpty(order.AdjustedOrderType)) orderProto.AdjustedOrderType = order.AdjustedOrderType;
            if (Util.IsValidValue(order.TriggerPrice)) orderProto.TriggerPrice = order.TriggerPrice;
            if (Util.IsValidValue(order.AdjustedStopPrice)) orderProto.AdjustedStopPrice = order.AdjustedStopPrice;
            if (Util.IsValidValue(order.AdjustedStopLimitPrice)) orderProto.AdjustedStopLimitPrice = order.AdjustedStopLimitPrice;
            if (Util.IsValidValue(order.AdjustedTrailingAmount)) orderProto.AdjustedTrailingAmount = order.AdjustedTrailingAmount;
            if (Util.IsValidValue(order.AdjustableTrailingUnit)) orderProto.AdjustableTrailingUnit = order.AdjustableTrailingUnit;
            if (Util.IsValidValue(order.LmtPriceOffset)) orderProto.LmtPriceOffset = order.LmtPriceOffset;

            List<protobuf.OrderCondition> orderConditionList = createConditionsProto(order);
            if (orderConditionList != null && orderConditionList.Any()) orderProto.Conditions.Add(orderConditionList);
            if (order.ConditionsCancelOrder) orderProto.ConditionsCancelOrder = order.ConditionsCancelOrder;
            if (order.ConditionsIgnoreRth) orderProto.ConditionsIgnoreRth = order.ConditionsIgnoreRth;

            if (!Util.StringIsEmpty(order.ModelCode)) orderProto.ModelCode = order.ModelCode;
            if (!Util.StringIsEmpty(order.ExtOperator)) orderProto.ExtOperator = order.ExtOperator;

    	    protobuf.SoftDollarTier softDollarTier = createSoftDollarTierProto(order);
            if (softDollarTier != null) orderProto.SoftDollarTier = softDollarTier;

            if (Util.IsValidValue(order.CashQty)) orderProto.CashQty = order.CashQty;
            if (!Util.StringIsEmpty(order.Mifid2DecisionMaker)) orderProto.Mifid2DecisionMaker = order.Mifid2DecisionMaker;
            if (!Util.StringIsEmpty(order.Mifid2DecisionAlgo)) orderProto.Mifid2DecisionAlgo = order.Mifid2DecisionAlgo;
            if (!Util.StringIsEmpty(order.Mifid2ExecutionTrader)) orderProto.Mifid2ExecutionTrader = order.Mifid2ExecutionTrader;
            if (!Util.StringIsEmpty(order.Mifid2ExecutionAlgo)) orderProto.Mifid2ExecutionAlgo = order.Mifid2ExecutionAlgo;
            if (order.DontUseAutoPriceForHedge) orderProto.DontUseAutoPriceForHedge = order.DontUseAutoPriceForHedge;
            if (order.IsOmsContainer) orderProto.IsOmsContainer = order.IsOmsContainer;
            if (order.DiscretionaryUpToLimitPrice) orderProto.DiscretionaryUpToLimitPrice = order.DiscretionaryUpToLimitPrice;
            if (order.UsePriceMgmtAlgo.HasValue) orderProto.UsePriceMgmtAlgo = order.UsePriceMgmtAlgo.Value ? 1 : 0;
            if (Util.IsValidValue(order.Duration)) orderProto.Duration = order.Duration;
            if (Util.IsValidValue(order.PostToAts)) orderProto.PostToAts = order.PostToAts;
            if (!Util.StringIsEmpty(order.AdvancedErrorOverride)) orderProto.AdvancedErrorOverride = order.AdvancedErrorOverride;
            if (!Util.StringIsEmpty(order.ManualOrderTime)) orderProto.ManualOrderTime = order.ManualOrderTime;
            if (Util.IsValidValue(order.MinTradeQty)) orderProto.MinTradeQty = order.MinTradeQty;
            if (Util.IsValidValue(order.MinCompeteSize)) orderProto.MinCompeteSize = order.MinCompeteSize;
            if (Util.IsValidValue(order.CompeteAgainstBestOffset)) orderProto.CompeteAgainstBestOffset = order.CompeteAgainstBestOffset;
            if (Util.IsValidValue(order.MidOffsetAtWhole)) orderProto.MidOffsetAtWhole = order.MidOffsetAtWhole;
            if (Util.IsValidValue(order.MidOffsetAtHalf)) orderProto.MidOffsetAtHalf = order.MidOffsetAtHalf;
            if (!Util.StringIsEmpty(order.CustomerAccount)) orderProto.CustomerAccount = order.CustomerAccount;
            if (order.ProfessionalCustomer) orderProto.ProfessionalCustomer = order.ProfessionalCustomer;
            if (!Util.StringIsEmpty(order.BondAccruedInterest)) orderProto.BondAccruedInterest = order.BondAccruedInterest;
            if (order.IncludeOvernight) orderProto.IncludeOvernight = order.IncludeOvernight;
            if (Util.IsValidValue(order.ManualOrderIndicator)) orderProto.ManualOrderIndicator = order.ManualOrderIndicator;
            if (!Util.StringIsEmpty(order.Submitter)) orderProto.Submitter = order.Submitter;
            if (order.AutoCancelParent) orderProto.AutoCancelParent = order.AutoCancelParent;
            if (order.ImbalanceOnly) orderProto.ImbalanceOnly = order.ImbalanceOnly;

            return orderProto;
        }

        public static List<protobuf.OrderCondition> createConditionsProto(Order order) 
        {
            List<protobuf.OrderCondition> orderConditionList = new List<protobuf.OrderCondition>();
            if (order.Conditions != null && order.Conditions.Count > 0) {
                foreach (OrderCondition condition in order.Conditions) {
                    OrderConditionType type = condition.Type;
                    protobuf.OrderCondition orderConditionProto = null;
                    switch(type) {
                        case OrderConditionType.Price:
                            orderConditionProto = createPriceConditionProto(condition);
                            break;
                        case OrderConditionType.Time:
                            orderConditionProto = createTimeConditionProto(condition);
                            break;
                        case OrderConditionType.Margin:
                            orderConditionProto = createMarginConditionProto(condition);
                            break;
                        case OrderConditionType.Execution:
                            orderConditionProto = createExecutionConditionProto(condition);
                            break;
                        case OrderConditionType.Volume:
                            orderConditionProto = createVolumeConditionProto(condition);
                            break;
                        case OrderConditionType.PercentCange:
                            orderConditionProto = createPercentChangeConditionProto(condition);
                            break;
                    }
                    if (orderConditionProto != null) {
                        orderConditionList.Add(orderConditionProto);
                    }
                }
            }
            return orderConditionList;
        }

        private static protobuf.OrderCondition createOrderConditionProto(OrderCondition condition) 
        {
            int type = (int)condition.Type;
            bool isConjunctionConnection = condition.IsConjunctionConnection;
            protobuf.OrderCondition orderConditionProto = new protobuf.OrderCondition();
            if (Util.IsValidValue(type)) orderConditionProto.Type = type;
            orderConditionProto.IsConjunctionConnection = isConjunctionConnection;
            return orderConditionProto;
        }

        private static protobuf.OrderCondition createOperatorConditionProto(OrderCondition condition)
        {
            protobuf.OrderCondition orderConditionProto = createOrderConditionProto(condition);
            OperatorCondition operatorCondition = (OperatorCondition)condition; 
            bool isMore = operatorCondition.IsMore;
            protobuf.OrderCondition operatorConditionProto = new protobuf.OrderCondition();
            operatorConditionProto.MergeFrom(orderConditionProto);
            operatorConditionProto.IsMore = isMore;
            return operatorConditionProto;
        }

        private static protobuf.OrderCondition createContractConditionProto(OrderCondition condition) 
        {
            protobuf.OrderCondition orderConditionProto = createOperatorConditionProto(condition);
            ContractCondition contractCondition = (ContractCondition)condition; 
            int conId = contractCondition.ConId;
            string exchange = contractCondition.Exchange;
            protobuf.OrderCondition contractConditionProto = new protobuf.OrderCondition();
            contractConditionProto.MergeFrom(orderConditionProto);
            if (Util.IsValidValue(conId)) contractConditionProto.ConId = conId;
            if (!Util.StringIsEmpty(exchange)) contractConditionProto.Exchange = exchange;
            return contractConditionProto;
        }

        private static protobuf.OrderCondition createPriceConditionProto(OrderCondition condition) 
        {
            protobuf.OrderCondition orderConditionProto = createContractConditionProto(condition);
            PriceCondition priceCondition = (PriceCondition)condition; 
            double price = priceCondition.Price;
            int triggerMethod = (int)priceCondition.TriggerMethod;
            protobuf.OrderCondition priceConditionProto = new protobuf.OrderCondition();
            priceConditionProto.MergeFrom(orderConditionProto);
            if (Util.IsValidValue(price)) priceConditionProto.Price = price;
            if (Util.IsValidValue(triggerMethod)) priceConditionProto.TriggerMethod = triggerMethod;
            return priceConditionProto;
        }

        private static protobuf.OrderCondition createTimeConditionProto(OrderCondition condition) 
        {
            protobuf.OrderCondition operatorConditionProto = createOperatorConditionProto(condition);
            TimeCondition timeCondition = (TimeCondition)condition; 
            string time = timeCondition.Time;
            protobuf.OrderCondition timeConditionProto = new protobuf.OrderCondition();
            timeConditionProto.MergeFrom(operatorConditionProto);
            if (!Util.StringIsEmpty(time)) timeConditionProto.Time = time;
            return timeConditionProto;
        }

        private static protobuf.OrderCondition createMarginConditionProto(OrderCondition condition)
        {
            protobuf.OrderCondition operatorConditionProto = createOperatorConditionProto(condition);
            MarginCondition marginCondition = (MarginCondition)condition; 
            int percent = marginCondition.Percent;
            protobuf.OrderCondition marginConditionProto = new protobuf.OrderCondition();
            marginConditionProto.MergeFrom(operatorConditionProto);
            if (Util.IsValidValue(percent)) marginConditionProto.Percent = percent;
            return marginConditionProto;
        }

        private static protobuf.OrderCondition createExecutionConditionProto(OrderCondition condition) 
        {
            protobuf.OrderCondition orderConditionProto = createOrderConditionProto(condition);
            ExecutionCondition executionCondition = (ExecutionCondition)condition; 
            string secType = executionCondition.SecType;
            string exchange = executionCondition.Exchange;
            string symbol = executionCondition.Symbol;
            protobuf.OrderCondition executionConditionProto = new protobuf.OrderCondition();
            executionConditionProto.MergeFrom(orderConditionProto);
            if (!Util.StringIsEmpty(secType)) executionConditionProto.SecType = secType;
            if (!Util.StringIsEmpty(exchange)) executionConditionProto.Exchange = exchange;
            if (!Util.StringIsEmpty(symbol)) executionConditionProto.Symbol = symbol;
            return executionConditionProto;
        }

        private static protobuf.OrderCondition createVolumeConditionProto(OrderCondition condition) 
        {
            protobuf.OrderCondition orderConditionProto = createContractConditionProto(condition);
            VolumeCondition volumeCondition = (VolumeCondition)condition; 
            int volume = volumeCondition.Volume;
            protobuf.OrderCondition volumeConditionProto = new protobuf.OrderCondition();
            volumeConditionProto.MergeFrom(orderConditionProto);
            if (Util.IsValidValue(volume)) volumeConditionProto.Volume = volume;
            return volumeConditionProto;
        }

        private static protobuf.OrderCondition createPercentChangeConditionProto(OrderCondition condition) 
        {
            protobuf.OrderCondition orderConditionProto = createContractConditionProto(condition);
            PercentChangeCondition percentChangeCondition = (PercentChangeCondition)condition; 
            double changePercent = percentChangeCondition.ChangePercent;
            protobuf.OrderCondition percentChangeConditionProto = new protobuf.OrderCondition();
            percentChangeConditionProto.MergeFrom(orderConditionProto);
            if (Util.IsValidValue(changePercent)) percentChangeConditionProto.ChangePercent = changePercent;
            return percentChangeConditionProto;
        }

        public static protobuf.SoftDollarTier createSoftDollarTierProto(Order order) 
        {
            SoftDollarTier tier = order.Tier;
            if (tier == null) {
                return null;
            }

            protobuf.SoftDollarTier softDollarTierProto = new protobuf.SoftDollarTier();
            if (!Util.StringIsEmpty(tier.Name)) softDollarTierProto.Name = tier.Name;
            if (!Util.StringIsEmpty(tier.Value)) softDollarTierProto.Value = tier.Value;
            if (!Util.StringIsEmpty(tier.DisplayName)) softDollarTierProto.DisplayName = tier.DisplayName;
            return softDollarTierProto;
        }

        public static protobuf.Contract createContractProto(Contract contract, Order order) 
        {
            protobuf.Contract contractProto = new protobuf.Contract();
            if (Util.IsValidValue(contract.ConId)) contractProto.ConId = contract.ConId;
            if (!Util.StringIsEmpty(contract.Symbol)) contractProto.Symbol = contract.Symbol;
            if (!Util.StringIsEmpty(contract.SecType)) contractProto.SecType = contract.SecType;
            if (!Util.StringIsEmpty(contract.LastTradeDateOrContractMonth)) contractProto.LastTradeDateOrContractMonth = contract.LastTradeDateOrContractMonth;
            if (Util.IsValidValue(contract.Strike)) contractProto.Strike = contract.Strike;
            if (!Util.StringIsEmpty(contract.Right)) contractProto.Right = contract.Right;
            if (!Util.StringIsEmpty(contract.Multiplier)) contractProto.Multiplier = Util.StringToDoubleMax(contract.Multiplier);
            if (!Util.StringIsEmpty(contract.Exchange)) contractProto.Exchange = contract.Exchange;
            if (!Util.StringIsEmpty(contract.PrimaryExch)) contractProto.PrimaryExch = contract.PrimaryExch;
            if (!Util.StringIsEmpty(contract.Currency)) contractProto.Currency = contract.Currency;
            if (!Util.StringIsEmpty(contract.LocalSymbol)) contractProto.LocalSymbol = contract.LocalSymbol;
            if (!Util.StringIsEmpty(contract.TradingClass)) contractProto.TradingClass = contract.TradingClass;
            if (!Util.StringIsEmpty(contract.SecIdType)) contractProto.SecIdType = contract.SecIdType;
            if (!Util.StringIsEmpty(contract.SecId)) contractProto.SecId = contract.SecId;
            if (contract.IncludeExpired) contractProto.IncludeExpired = contract.IncludeExpired;
            if (!Util.StringIsEmpty(contract.ComboLegsDescription)) contractProto.ComboLegsDescrip = contract.ComboLegsDescription;
            if (!Util.StringIsEmpty(contract.Description)) contractProto.Description = contract.Description;
            if (!Util.StringIsEmpty(contract.IssuerId)) contractProto.IssuerId = contract.IssuerId;

            List<protobuf.ComboLeg> comboLegProtoList = createComboLegProtoList(contract, order);
            if (comboLegProtoList != null) {
                contractProto.ComboLegs.AddRange(comboLegProtoList);
            }
            protobuf.DeltaNeutralContract deltaNeutralContractProto = createDeltaNeutralContractProto(contract);
            if (deltaNeutralContractProto != null) {
               contractProto.DeltaNeutralContract = deltaNeutralContractProto;
            }
            return contractProto;
        }

        public static protobuf.DeltaNeutralContract createDeltaNeutralContractProto(Contract contract) 
        {
            if (contract.DeltaNeutralContract == null) {
                return null;
            }
            DeltaNeutralContract deltaNeutralContract = contract.DeltaNeutralContract;
            protobuf.DeltaNeutralContract deltaNeutralContractProto = new protobuf.DeltaNeutralContract();
            if (Util.IsValidValue(deltaNeutralContract.ConId)) deltaNeutralContractProto.ConId = deltaNeutralContract.ConId;
            if (Util.IsValidValue(deltaNeutralContract.Delta)) deltaNeutralContractProto.Delta = deltaNeutralContract.Delta;
            if (Util.IsValidValue(deltaNeutralContract.Price)) deltaNeutralContractProto.Price = deltaNeutralContract.Price;
            return deltaNeutralContractProto;
        }

        public static List<protobuf.ComboLeg> createComboLegProtoList(Contract contract, Order order) 
        {
            List<ComboLeg> comboLegs = contract.ComboLegs;
            if (comboLegs == null || !comboLegs.Any()) {
                return null;
            }
            List<protobuf.ComboLeg> comboLegProtoList = new List<protobuf.ComboLeg>();
            for(int i = 0; i < comboLegs.Count; i++) {
                ComboLeg comboLeg = comboLegs.ElementAt(i);
                double perLegPrice = double.MaxValue;
                if (i < order.OrderComboLegs.Count) {
                    perLegPrice = order.OrderComboLegs.ElementAt(i).Price;
                }
                protobuf.ComboLeg comboLegProto = createComboLegProto(comboLeg, perLegPrice);
                comboLegProtoList.Add(comboLegProto);
            }
            return comboLegProtoList;
        }

        public static protobuf.ComboLeg createComboLegProto(ComboLeg comboLeg, double perLegPrice) 
        {
            protobuf.ComboLeg comboLegProto = new protobuf.ComboLeg();
            if (Util.IsValidValue(comboLeg.ConId)) comboLegProto.ConId = comboLeg.ConId;
            if (Util.IsValidValue(comboLeg.Ratio)) comboLegProto.Ratio = comboLeg.Ratio;
            if (!Util.StringIsEmpty(comboLeg.Action)) comboLegProto.Action = comboLeg.Action;
            if (!Util.StringIsEmpty(comboLeg.Exchange)) comboLegProto.Exchange = comboLeg.Exchange;
            if (Util.IsValidValue(comboLeg.OpenClose)) comboLegProto.OpenClose = comboLeg.OpenClose;
            if (Util.IsValidValue(comboLeg.ShortSaleSlot)) comboLegProto.ShortSalesSlot = comboLeg.ShortSaleSlot;
            if (!Util.StringIsEmpty(comboLeg.DesignatedLocation)) comboLegProto.DesignatedLocation = comboLeg.DesignatedLocation;
            if (Util.IsValidValue(comboLeg.ExemptCode)) comboLegProto.ExemptCode = comboLeg.ExemptCode;
            if (Util.IsValidValue(perLegPrice)) comboLegProto.PerLegPrice = perLegPrice;
            return comboLegProto;
        }

        public static protobuf.CancelOrderRequest createCancelOrderRequestProto(int id, OrderCancel orderCancel) 
        {
            protobuf.CancelOrderRequest cancelOrderRequestProto = new protobuf.CancelOrderRequest();
            if (Util.IsValidValue(id)) cancelOrderRequestProto.OrderId = id;
            protobuf.OrderCancel orderCancelProto = createOrderCancelProto(orderCancel);
            if (orderCancelProto != null) cancelOrderRequestProto.OrderCancel = orderCancelProto;
            return cancelOrderRequestProto;
        }

        public static protobuf.GlobalCancelRequest createGlobalCancelRequestProto(OrderCancel orderCancel) 
        {
            protobuf.GlobalCancelRequest globalCancelRequestProto = new protobuf.GlobalCancelRequest();
            protobuf.OrderCancel orderCancelProto = createOrderCancelProto(orderCancel);
            if (orderCancelProto != null) globalCancelRequestProto.OrderCancel = orderCancelProto;
            return globalCancelRequestProto;
        }

        public static protobuf.OrderCancel createOrderCancelProto(OrderCancel orderCancel) 
        {
            protobuf.OrderCancel orderCancelProto = new protobuf.OrderCancel();
            if (!Util.StringIsEmpty(orderCancel.ManualOrderCancelTime)) orderCancelProto.ManualOrderCancelTime = orderCancel.ManualOrderCancelTime;
            if (!Util.StringIsEmpty(orderCancel.ExtOperator)) orderCancelProto.ExtOperator = orderCancel.ExtOperator;
            if (Util.IsValidValue(orderCancel.ManualOrderIndicator)) orderCancelProto.ManualOrderIndicator = orderCancel.ManualOrderIndicator;
            return orderCancelProto;
        }
    }
}
