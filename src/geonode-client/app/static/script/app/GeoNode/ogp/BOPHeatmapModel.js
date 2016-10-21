Ext.namespace("GeoNode");

GeoNode.BOPHeatmapModel = Ext.extend(Ext.util.Observable, {

    radiusAdjust: 1.1,

    gradientStops: [
      0x00000000,
      0x0000dfff,
      0x0000dfff,
      0x00effeff,
      0x00ff42ff,
      0x00ff42ff,
      0xfeec30ff,
      0xfeec30ff,
      0xff5f00ff,
      0xff0000ff],

    constructor: function(config) {
      var self = this;
      Ext.apply(this, config);

      this.map = GeoExt.MapPanel.guess().map;
      this.map.events.on({
          'moveend': this.updateHeatMapLayers,
          scope: this
      });

      if (config && config.params && config.params["q.text"]) {
          this.requestHeatmap(config.params);
      }

      Ext.QuickTips.init();

      this.tooltip = new Ext.ToolTip({
          html: 'test',
          cls: 'ogp-tooltip',
          hideDelay: 0,
          showDelay: 0,
          width: 80
        });
    },

    /**
     * Request heatmap with the given parameters
     * @param {Object} params request parameters due to API
     */
    requestHeatmap: function(params) {
      Ext.Ajax.request({
          url: GeoNode.bopTweetSearchBackend,
          method: 'GET',
          params: params,
          waitMsg: "{% trans 'Searching for tweets...' %}",
          success: function(response) {
              if (response && response.responseText){
                  var respHeatmap = Ext.util.JSON.decode(response.responseText);
                  if (respHeatmap["a.matchDocs"] > 0) {
                      this.drawHeatmapOpenLayers(params, respHeatmap);
                      var searchWin = Ext.getCmp('ge_searchWindow');
                      if (searchWin){
                          Ext.getCmp('ge_searchWindow').hide();
                      }
                  } else {
                      var msg = "The configured heatmap contains no facets";
                      Ext.Msg.show({
                          title: "{% trans 'Warning' %}",
                          msg: msg,
                          minWidth: 200,
                          modal: true,
                          icon: Ext.Msg.WARN,
                          buttons: Ext.Msg.OK
                      });
                  }
              }
          },
          failure: function(response, form) {
              var msg = Ext.util.JSON.decode(response.responseText).message;

              var error_message = '<ul>';
              error_message += '<li>' + msg + '</li>';
              error_message += '</ul>'

              Ext.Msg.show({
                  title: "{% trans 'Error' %}",
                  msg: error_message,
                  minWidth: 200,
                  modal: true,
                  icon: Ext.Msg.ERROR,
                  buttons: Ext.Msg.OK
              });
          },
          scope: this
      });
    },

    /**
     * Creates a new `Heatmap.Layer` instance with responsed heatmap from API
     * @param {Object} heatMapParams original request parameters from form
     * @param {Object} respHeatmap heatmap parameters as JSON response from API
     */
    drawHeatmapOpenLayers: function(heatMapParams, respHeatmap){

        // don't do anything, if heatmap parameters are empty
        var heatmap = respHeatmap["a.hm"];
        if (heatmap == null){
            return;
        };

        var heatMapLayerName = heatMapParams["q.text"];

        var heatmapLayer = new Heatmap.Layer(heatMapLayerName);

        this.heatmapLayer = heatmapLayer;

        // set additional abstract property to be used as tooltip on
        // mouseover event on layer record in layertree
        this.heatmapLayer["abstract"] = heatMapLayerName;

        // store the request parameters (q.time, q.bbox, q.text, q.user,
        // d.docs.limit and d.docs.sort) to reuse it on heatmap update
        this.heatmapLayer["requestParams"] = heatMapParams;

        this.heatmapLayer.points = [];

        var counts_ints2D = heatmap.counts_ints2D;
        var gridLevel = heatmap.gridLevel;
        var gridRows = heatmap.rows;
        var gridColumns = heatmap.columns;
        var minMaxValue = this.heatmapMinMax(counts_ints2D, gridRows, gridColumns);
        var maxValue = minMaxValue[1];
        if (maxValue == -1) {
            return;
        }
        var minX = heatmap.minX;
        var maxX = heatmap.maxX;
        var dx = maxX - minX;
        var minY = heatmap.minY;
        var maxY = heatmap.maxY;
        var dy = maxY - minY;

        var sx = dx / gridColumns;
        var sy = dy / gridRows;
        var classifications = this.getClassifications(heatmap);
        var colorGradient = this.getColorGradient(this.gradientStops, classifications);
        this.heatmapLayer.setGradientStops(colorGradient);

        for (var i = 0 ; i < gridRows ; i++){
            for (var j = 0 ; j < gridColumns ; j++){
              try{
                var hmVal = counts_ints2D[counts_ints2D.length - i - 1][j];
                if (hmVal && hmVal !== null){
                    var lat = minY + i*sy + (0.5 * sy);
                    var lon = minX + j*sx + (0.5 * sx);
                    var radius = this.computeRadius(lat, lon, sx, sy);
                    var mercator = this.WGS84ToMercator(lon, lat);
                    var scaledValue = Math.min(classifications[classifications.length-1] / maxValue, hmVal / maxValue);
                    //var scaledValue = this.rescaleHeatmapValue(hmVal, minMaxValue);
                    var radiusFactor = this.getRadiusFactor();
                    this.heatmapLayer.addSource(
                      new Heatmap.Source(mercator, radius*radiusFactor*this.radiusAdjust, scaledValue)
                    );
                }
              }
              catch (error){
                console.log("error making heatmap: " + error);
              }
            }
        }
        this.heatmapLayer.setOpacity(0.50);

        if(this.map.getLayersByName(heatMapLayerName).length == 0 && this.heatmapLayer.points.length > 0){

            this.layertree = app.layerTree;
            var folderName = "BOP Heatmap Layers";

            // TODO: this is WIP state --> source don't be created correct yet
            // so the heatmap layer cannot be persisted
            // var sourceConfig = {
            //     "config":{
            //         "ptype":"gxp_olsource"
            //     },
            //     "type": "Heatmap.Layer",
            //     "source": 5,
            //     "name": this.heatmapLayer.name,
            //     "visibility": true,
            //     "fixed": true,
            //     "group": folderName
            // };
            //var source = app.addLayerSource(sourceConfig);
            //var heatmapRecord = source.createLayerRecord(sourceConfig);
            //app.mapPanel.layers.add([heatmapRecord]);

            this.map.addLayer(this.heatmapLayer);
            this.map.raiseLayer(this.heatmapLayer, this.map.layers.length);
            this.layertree.addCategoryFolder({group: folderName}, true);
            this.createLayerTreeNode(folderName, this.heatmapLayer);
        } else {
            this.heatmapLayer.redraw();
        }
    },

    getClassifications : function(facetHeatmap)
      {
      var flatArray = [];
      var count = 0;
      var maxValue = 0;
      for (var i = 0; i < facetHeatmap.counts_ints2D.length; i++) 
      {
          if (facetHeatmap.counts_ints2D[i] != null)  // entire row can be null
          for (var j = 0 ; j < facetHeatmap.counts_ints2D[i].length ; j++)
              {
              var currentValue = facetHeatmap.counts_ints2D[i][j];
              if (currentValue != null) // && facetHeatmap.counts_ints2D[i][j] != 0)
                  {
              var flatArray = flatArray.concat(currentValue);
              if (currentValue > maxValue) maxValue = currentValue;
              count++;
              
                  }
          }
      };
      // jenks classification takes too long on lots of data
      // so we just sample larger data sets
      reducedArray = [];
      var period = Math.ceil(count / 300);
      period = Math.min(period, 6);
      if (period > 1)
      {
          for (i = 0 ; i < flatArray.length ; i = i + period)
          reducedArray.push(flatArray[i]);
          reducedArray.push(maxValue);  // make sure largest value gets in, doesn't matter much if duplicated
      }
      else
          reducedArray = flatArray;
      var series = new geostats(reducedArray);
      numberOfClassifications = this.gradientStops.length - 1;
      var classifications = series.getClassJenks(numberOfClassifications);

      var lastExtraZero = -1;
      for (var i = classifications.length - 1 ; i > 0 ; i--)
          if (classifications[i] == 0 && lastExtraZero == -1)
          lastExtraZero = i;
      if (lastExtraZero > 0)
          classifications = classifications.slice(lastExtraZero)
      return classifications;
    },
    getColorGradient: function(colors, classifications)
      {
      colorGradient = {};
      maxValue = classifications[classifications.length - 1];
      if (classifications.length != colors.length)
          console.log("!!! number of classifications do not match colors", classifications.length, colors.length);
      for (var i = 0 ; i < classifications.length ; i++)
      {
          value = classifications[i];
          scaledValue = value / maxValue;
          scaledValue = Number(scaledValue.toFixed(4));
          if (scaledValue < 0)
          scaledValue = 0;
          colorGradient[scaledValue] = colors[i];
      }
      return colorGradient;
    },
    /**
     * Update heatmap layer after map extent was change (on zoom or pan event)
     */
    updateHeatMapLayers: function(){
        var heatmapLayers = this.map.getLayersByClass('Heatmap.Layer');
        Ext.each(heatmapLayers, function(hmLayer){
            // update spatial bbox with the current map extent
            hmLayer.requestParams["q.geo"] = this.updateBbox();
            this.requestHeatmap(hmLayer.requestParams);
        },this);
    },

    /**
     * Create new tree node for the added heatmap layer. This will be placed
     * in "BOP Heatmap Layers" folder of the layer tree.
     * @param {String} folderName folder name
     * @param {Heatmap.Layer} layer layer to be added
     */
    createLayerTreeNode: function(folderName, layer){
        var ltPanel = Ext.getCmp('treecontent');
        var rootNode = this.layertree.tree.getRootNode();
        var parentNode;
        rootNode.cascade(function(node){
            if (node.text === folderName){
                parentNode = node;
            }
        });
        if (parentNode){
            parentNode.appendChild({
                plugins: [{ptype: 'gx_layer'}],
                layer: layer,
                text: layer.name,
                layerStore: this.layertree.target.mapPanel.layers,
                leaf: true
            });
        }
    },

    getRadiusFactor: function(){
        var factor = [1.6, 1.5, 2.6, 2.4, 2.2, 1.8, 2., 2., 2.];
        var zoomLevel = this.map.getZoom();
        if (zoomLevel <1){
          return 1;
        };

        var index = zoomLevel - 1;
        if (index > factor.length - 1){
          return factor[factor.length - 1];
        }

        var value = factor[index];
        return value;
    },

    heatmapMinMax: function (heatmap, sLat, sLon){
      var max = -1;
      var min = Number.MAX_VALUE;
      for (var i = 0 ; i < sLat ; i++){
        var currentRow = heatmap[i];
        if (currentRow == null){
            heatmap[i] = currentRow = []
        }
        for (var j = 0 ; j < sLon ; j++){
          if (currentRow[j] == null){
            currentRow[j] = -1;
          }

          if (currentRow[j] > max){
            max = currentRow[j];
          }

          if (currentRow[j] < min && currentRow[j] > -1){
            min = currentRow[j];
          }
        }
      }
      return [min, max];
    },

    rescaleHeatmapValue: function(value, minMaxValue){
        if (value == null){
          return 0;
        };

        if (value == -1){
          return -1;
        };

        if (value == 0){
          return 0;
        };

        if ((minMaxValue[1] - minMaxValue[0]) === 0){
            return 0;
        }
        return (value - minMaxValue[0]) / (minMaxValue[1] - minMaxValue[0]);
    },

    computeRadius: function(latitude, longitude, latitudeStepSize, longitudeStepSize){
      var mercator1 = this.WGS84ToMercator(longitude, latitude);
      var pixel1 = this.map.getPixelFromLonLat(mercator1);
      var mercator2 = this.WGS84ToMercator(longitude + longitudeStepSize, latitude + latitudeStepSize);
      var pixel2 = this.map.getPixelFromLonLat(mercator2);
      var deltaLatitude = Math.abs(pixel1.x - pixel2.x);
      var deltaLongitude = Math.abs(pixel1.y - pixel2.y);
      var delta = Math.max(deltaLatitude, deltaLongitude);
      return Math.ceil(delta / 2.);
    },

    WGS84ToMercator: function(the_lon, the_lat) {
        // returns -infinity for -90.0 lat; a bug?
        var lat = parseFloat(the_lat);
        var lon = parseFloat(the_lon);
        if (lat >= 90) {
          lat = 89.99;
        }
        if (lat <= -90) {
          lat = -89.99;
        }
        if (lon >= 180) {
          lon = 179.99;
        }
        if (lon <= -180) {
          lon = -179.99;
        }
        return OpenLayers.Layer.SphericalMercator.forwardMercator(lon, lat);
    },

    /**
     * Compute new bounding box from the current map extent and return it as
     * string that can be read by API (e.g. `[-90,-180 TO 90,180]`).
     * Additionaly a normalization of extent will be proceed to fit it to maximal
     * bounds (s. {@normalize} method)
     */
    updateBbox: function() {
        var wgs84extent = this.map.getExtent()
            .transform(this.map.getProjection(), 'EPSG:4326');
        var normWgs84extent = this.normalize(wgs84extent).toString().split(',');
        return "[" + normWgs84extent[1] + "," + normWgs84extent[0] + " TO " + normWgs84extent[3] + "," + normWgs84extent[2] + "]"
    },

    /**
     * Clamps given number `num` to be inside the allowed range from `min`
     * to `max`.
     * Will also work as expected if `max` and `min` are accidently swapped.
     *
     * @param {number} num The number to clamp.
     * @param {number} min The minimum allowed number.
     * @param {number} max The maximim allowed number.
     * @return {number} The clamped number.
     */
    clamp: function(num, min, max) {
        if (max < min) {
            var tmp = min;
            min = max;
            max = tmp;
        }
        return Math.min(Math.max(min, num), max);
    },

    /**
     * Determines whether passed longitude is outside of the range `-180`
     * and `+180`.
     *
     * @param {number} lon The longitude to check.
     * @return {boolean} Whether the longitude is outside of the range
     *  -180` and `+180`.
     */
    outsideLonRange: function(lon) {
        return lon < -180 || lon > 180;
    },

    /**
     * Determines whether passed latitude is outside of the range `-90` and
     * `+90`.
     * @param {number} lat The longitude to check.
     * @return {boolean} Whether the latitude is outside of the range `-90`
     *  and `+90`.
     */
    outsideLatRange: function(lat) {
        return lat < -90 || lat > 90;
    },

    /**
     * Clamps given longitude to be inside the allowed range from `-180` to
     * `+180`.
     * @param {number} lon The longitude to fit / clamp.
     * @return {number} The fitted / clamped longitude.
     */
    clampLon: function(lon) {
        return this.clamp(lon, -180, 180);
    },

    /**
     * Clamps given latitude to be inside the allowed range from `-90` to
     * `+90`.
     * @param {number} lat The latitude to fit / clamp.
     * @return {number} The fitted / clamped latitude.
     */
    clampLat: function(lat) {
        return this.clamp(lat, -90, 90);
    },

    /**
     * Normalizes an `EPSG:4326` extent which may stem from multiple worlds
     * so that the returned extent always is within the bounds of the one
     * true `EPSG:4326` world extent `[-180, -90, 180, 90]`.
     *
     * Examples:
     *
     *     // valid world in, returned as-is:
     *     normalize([-180, -90, 180, 90])  // => [-180, -90, 180, 90]
     *
     *     // valid extent in world in, returned as-is:
     *     normalize([-160, -70, 150, 70])  // => [-160, -70, 150, 70]
     *
     *     // shifted one degree westwards, returns one-true world:
     *     normalize([-181, -90, 179, 90])  // => [-180, -90, 180, 90]
     *
     *     // shifted one degree eastwards, returns one-true world:
     *     normalize([-179, -90, 181, 90])  // => [-180, -90, 180, 90]);
     *
     *     // shifted more than one world westwards, returns one-true world:
     *     normalize([-720, -90, -360, 90]) // => [-180, -90, 180, 90]);
     *
     *     // shifted to the south, returns one-true world:
     *     normalize([-180, -91, 180, 89])  // =>   [-180, -90, 180, 90]);
     *
     *     // multiple worlds, returns one-true world:
     *     normalize([-360, -90, 180, 90])  // =>   [-180, -90, 180, 90]);
     *
     *     // multiple worlds, returns one-true world:
     *     normalize([-360, -180, 180, 90]) // =>  [-180, -90, 180, 90]);
     *
     * @param {Array<number>} Extent to normalize: [minx, miny, maxx, maxy].
     * @return {Array<number>} Normalized extent: [minx, miny, maxx, maxy].
     */
    normalize: function(extent) {
        var minX = extent.left;
        var minY = extent.bottom;
        var maxX = extent.right;
        var maxY = extent.top;
        var width = Math.min(maxX - minX, 360);
        var height = Math.min(maxY - minY, 180);

        if (this.outsideLonRange(minX)) {
            minX = this.clampLon(minX);
            maxX = minX + width;
        } else if (this.outsideLonRange(maxX)) {
            maxX = this.clampLon(maxX);
            minX = maxX - width;
        }

        if (this.outsideLatRange(minY)) {
            minY = this.clampLat(minY);
            maxY = minY + height;
        } else if (this.outsideLatRange(maxY)) {
            maxY = this.clampLat(maxY);
            minY = maxY - height;
        }

        return [minX, minY, maxX, maxY];
    }
});
